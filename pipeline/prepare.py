"""Rohdaten (data/raw/) -> Zwischenstände (data/interim/).

Portierung von src/get_data/{results_data,accidents_data,bike_data}.py und
src/add_population.py (read_pop_new). Die Zwischenstände in data/interim/ sind
versioniert, `python -m pipeline build` braucht diese Schritte also nicht.

Öffentlich verfügbare Rohdaten (ASTRA-Unfälle, swissBOUNDARIES3D) werden bei
Bedarf von data.geo.admin.ch heruntergeladen. Die übrigen Rohdaten (ehemals
data.zip) sind nicht im Repo; fehlen sie, werden die betroffenen Schritte
übersprungen.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from . import paths


class RawDataMissingError(FileNotFoundError):
    """Rohdaten fehlen unter data/raw/."""


def require_raw(*files: Path) -> None:
    """Bricht mit einer verständlichen Meldung ab, wenn Rohdateien fehlen."""
    missing = [f for f in files if not f.exists()]
    if missing:
        listing = "\n".join(f"  - {f.relative_to(paths.ROOT_DIR)}" for f in missing)
        raise RawDataMissingError(
            "Rohdaten fehlen:\n"
            f"{listing}\n"
            "Die Rohdaten (ehemals data.zip) sind nicht im Repository und der Download-Link "
            "ist abgelaufen. Die Zwischenstände in data/interim/ sind versioniert; "
            "für das Endresultat genügt `python -m pipeline build`."
        )


def download(url: str, target: Path) -> Path:
    """Lädt ein ZIP herunter und entpackt die Datei ``target.name`` nach ``target``."""
    if target.exists():
        return target
    print(f"Lade {url} …")
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    member = next(n for n in archive.namelist() if Path(n).name == target.name)
    target.write_bytes(archive.read(member))
    return target


def download_zip_members(url: str, members: list[str], target_dir: Path) -> list[Path]:
    """Lädt einzelne Dateien aus einem entfernten ZIP (HTTP-Range), ohne das ganze Archiv.

    Nützlich für swissTLM3D (3.4 GB), von dem nur die Bodenbedeckung gebraucht wird.
    """
    import struct
    import zlib

    def fetch(start: int, end: int) -> bytes:
        req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read()

    targets = [target_dir / Path(m).name for m in members]
    if all(t.exists() for t in targets):
        return targets
    target_dir.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
        size = int(r.headers["Content-Length"])
    tail = fetch(max(0, size - 65_536), size - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    cd_size, cd_offset = struct.unpack("<II", tail[eocd + 12 : eocd + 20])
    if cd_offset == 0xFFFFFFFF:  # ZIP64
        z64 = tail.rfind(b"PK\x06\x06")
        cd_size, cd_offset = struct.unpack("<QQ", tail[z64 + 40 : z64 + 56])
    cd = fetch(cd_offset, cd_offset + cd_size - 1)

    entries, pos = {}, 0
    while cd[pos : pos + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[pos + 10 : pos + 12])[0]
        csize, usize = struct.unpack("<II", cd[pos + 20 : pos + 28])
        n_len, e_len, c_len = struct.unpack("<HHH", cd[pos + 28 : pos + 34])
        offset = struct.unpack("<I", cd[pos + 42 : pos + 46])[0]
        name = cd[pos + 46 : pos + 46 + n_len].decode()
        extra = cd[pos + 46 + n_len : pos + 46 + n_len + e_len]
        k = 0
        while k < len(extra):  # ZIP64-Erweiterung: echte Grössen und Offset
            hid, hlen = struct.unpack("<HH", extra[k : k + 4])
            if hid == 1:
                vals = list(struct.unpack("<" + "Q" * (hlen // 8), extra[k + 4 : k + 4 + hlen]))
                if usize == 0xFFFFFFFF:
                    usize = vals.pop(0)
                if csize == 0xFFFFFFFF:
                    csize = vals.pop(0)
                if offset == 0xFFFFFFFF:
                    offset = vals.pop(0)
            k += 4 + hlen
        entries[name] = (method, csize, offset)
        pos += 46 + n_len + e_len + c_len

    for member, target in zip(members, targets, strict=True):
        if target.exists():
            continue
        method, csize, offset = entries[member]
        header = fetch(offset, offset + 29)
        n_len, e_len = struct.unpack("<HH", header[26:30])
        start = offset + 30 + n_len + e_len
        print(f"Lade {member} ({csize / 1e6:.0f} MB) …")
        data = fetch(start, start + csize - 1)
        target.write_bytes(zlib.decompress(data, -15) if method == 8 else data)
    return targets


def _to_lv95(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Setzt LV95, falls kein CRS vorhanden, sonst Transformation nach LV95."""
    if gdf.crs is None:
        return gdf.set_crs(paths.CRS)
    return gdf.to_crs(paths.CRS)


def _drop_aggregate_rows(df: pd.DataFrame, name_col: str) -> pd.DataFrame:
    """Entfernt Kantons- ('- ') und Bezirkszeilen ('>> ') aus STAT-TAB-Exporten.

    Gemeindezeilen haben das Format '......0001 Aeugst am Albis'.
    """
    names = df[name_col]
    return df.loc[~names.str.startswith(">>") & ~names.str.startswith("-")].copy()


# --------------------------------------------------------------------------
# Abstimmungsresultate + BFS-Gemeindegeometrien
# --------------------------------------------------------------------------
def read_bfs_municipalities(path: Path = paths.RAW_BFS_SHP) -> gpd.GeoDataFrame:
    """BFS-Gemeindegrenzen mit Nummer, Name, Bezirk, Kanton und Zentrumskoordinaten."""
    bfs = gpd.read_file(path)
    keep_cols = ["GMDNR", "GMDNAME", "BZNR", "KTNR", "E_CNTR", "N_CNTR", "geometry"]
    return _to_lv95(bfs[keep_cols])


def read_vote_results(path: Path = paths.RAW_RESULTS_XLSX) -> pd.DataFrame:
    """Abstimmungsresultate pro Gemeinde aus dem BFS-Excel."""
    results = pd.read_excel(path, sheet_name="data", header=0)
    results = results.dropna(axis=0)

    df = _drop_aggregate_rows(results, "GMDNAME")
    # '......0001 Aeugst am Albis' -> 'Aeugst am Albis'
    # (fixe Länge 6: bei einigen Gemeinden wird so der Name abgeschnitten, s. Bericht)
    df["GMDNAME"] = df["GMDNAME"].str[6:]
    df = df.drop(index=0)  # erste verbleibende Zeile ist das Total Schweiz
    df["GMDNR"] = df["GMDNR"].astype(int)
    return df


def results_with_geometries() -> gpd.GeoDataFrame:
    """Verknüpft Resultate und Gemeindegeometrien (inner join über GMDNR).

    Beide Tabellen haben 'GMDNAME' -> GMDNAME_x (Excel) und GMDNAME_y (BFS-Shapefile),
    wie im ursprünglichen Export.
    """
    require_raw(paths.RAW_BFS_SHP, paths.RAW_RESULTS_XLSX)
    merged = pd.merge(read_vote_results(), read_bfs_municipalities(), on=["GMDNR"])
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=paths.CRS)


# --------------------------------------------------------------------------
# Velounfälle
# --------------------------------------------------------------------------
ACCIDENT_COLUMNS = [
    "AccidentUID",
    "AccidentType_de",
    "AccidentSeverityCategory_de",
    "AccidentInvolvingPedestrian",
    "AccidentInvolvingBicycle",
    "RoadType_de",
    "AccidentLocation_CHLV95_E",
    "AccidentLocation_CHLV95_N",
    "CantonCode",
    "AccidentYear",
    "AccidentMonth",
]


def bicycle_accidents(path: Path = paths.RAW_ACCIDENTS_CSV) -> gpd.GeoDataFrame:
    """Unfälle mit Velobeteiligung von 2011 bis und mit ``paths.ACCIDENT_END`` (LV95)."""
    download(paths.ACCIDENTS_URL, path)
    df = pd.read_csv(path, usecols=ACCIDENT_COLUMNS, encoding="utf-8-sig")
    for col in ("AccidentInvolvingBicycle", "AccidentInvolvingPedestrian"):
        df[col] = df[col].astype(str).str.lower().eq("true")

    end_year, end_month = paths.ACCIDENT_END
    period = (df["AccidentYear"] < end_year) | (
        (df["AccidentYear"] == end_year) & (df["AccidentMonth"] <= end_month)
    )
    df = df.loc[df["AccidentInvolvingBicycle"] & period].reset_index(drop=True)

    # Geometrie direkt aus den LV95-Koordinaten der Unfallstelle
    geometry = gpd.points_from_xy(
        df["AccidentLocation_CHLV95_E"], df["AccidentLocation_CHLV95_N"], crs=paths.CRS
    )
    return gpd.GeoDataFrame(df, geometry=geometry, crs=paths.CRS)


# --------------------------------------------------------------------------
# Velowege (OSM + Veloland)
# --------------------------------------------------------------------------
def read_osm_cycleways(path: Path = paths.RAW_OSM_ROADS_SHP) -> gpd.GeoDataFrame:
    """OSM-Strassen gefiltert auf Velowege (code 5152), in LV95."""
    osm = gpd.read_file(path, columns=["osm_id", "code"])
    osm = osm.loc[osm["code"] == paths.OSM_CYCLEWAY_CODE, ["osm_id", "code", "geometry"]]
    osm = _to_lv95(osm)
    return osm.rename(columns={"osm_id": "OBJECTID"})


def read_veloland(path: Path = paths.RAW_VELOLAND_SHP) -> gpd.GeoDataFrame:
    """SchweizMobil-Veloland-Routen, in LV95."""
    veloland = gpd.read_file(path)
    return _to_lv95(veloland[["OBJECTID", "SHAPE_Leng", "Change_Dt", "geometry"]])


def bike_network() -> gpd.GeoDataFrame:
    """Vereinigt OSM-Velowege und Veloland-Routen in einem Layer."""
    require_raw(paths.RAW_OSM_ROADS_SHP, paths.RAW_VELOLAND_SHP)
    osm = read_osm_cycleways()
    veloland = read_veloland()
    bikes = pd.concat([osm, veloland], ignore_index=True)
    # OSM-IDs sind Strings, Veloland-IDs Zahlen -> einheitlich als Text (wie im Export)
    bikes["OBJECTID"] = bikes["OBJECTID"].astype(str)
    return gpd.GeoDataFrame(bikes, geometry="geometry", crs=paths.CRS)


# --------------------------------------------------------------------------
# Bevölkerung
# --------------------------------------------------------------------------
def population_from_raw(path: Path = paths.RAW_POPULATION_CSV) -> pd.DataFrame:
    """Ständige Wohnbevölkerung am 1.1.2021 pro Gemeinde (Port von read_pop_new)."""
    require_raw(path)
    raw = pd.read_csv(path, sep=",", encoding="Latin-1")
    raw = raw.drop(columns=["Jahr", "Geschlecht"])
    raw = raw.rename(
        columns={
            "Kanton (-) / Bezirk (>>) / Gemeinde (......)": "GMDNAME",
            "Bestand am 1. Januar": "POP_TOTAL",
        }
    )

    df = _drop_aggregate_rows(raw, "GMDNAME")
    # '......0001 Aeugst am Albis' -> '0001' -> BFS-Nummer
    df["BFSNR"] = df["GMDNAME"].str[6:].str[:4]
    df = df.drop(index=0)  # Total Schweiz
    df = df.reset_index(drop=True)
    df = df.drop(index=len(df) - 1)  # Fusszeile des STAT-TAB-Exports
    df["BFSNR"] = df["BFSNR"].astype(int)
    return df[["BFSNR", "POP_TOTAL"]]


def official_municipalities(path: Path = paths.RAW_BOUNDARIES_GPKG) -> gpd.GeoDataFrame:
    """Offizielle Hoheitsgebiete der Schweiz (swissBOUNDARIES3D, Stand 1.1.2023).

    Eine Zeile pro BFS-Nummer (Teilflächen zusammengefasst), 2D, LV95. Enthält neben
    den Gemeinden auch Kommunanzen und kantonale Seeflächen (``objektart``).
    """
    download(paths.BOUNDARIES_URL, path)
    gdf = gpd.read_file(
        path,
        layer="tlm_hoheitsgebiet",
        columns=["bfs_nummer", "name", "kantonsnummer", "objektart", "einwohnerzahl", "icc"],
    )
    gdf = gdf[gdf["icc"] == "CH"]
    gdf["geometry"] = gdf.geometry.force_2d()
    out = gdf.dissolve(
        by="bfs_nummer",
        aggfunc={
            "name": "first",
            "kantonsnummer": "first",
            "objektart": "first",
            "einwohnerzahl": "sum",
        },
    ).reset_index()
    return _to_lv95(out)


def lakes(path: Path = paths.RAW_LAKES_GPKG) -> gpd.GeoDataFrame:
    """Seeflächen aus swissTLM3D (Bodenbedeckung «Stehende Gewaesser»), LV95, 2D.

    Gleiche Datengrundlage wie die Gewässer der swisstopo-Karten. Nur Flächen ab
    ``paths.MIN_LAKE_AREA`` m² (kleine Weiher sind für die Karte unerheblich).
    """
    if path.exists():
        return gpd.read_file(path)
    raw_dir = paths.RAW_DIR / "swisstlm3d"
    parts = []
    for region in ("OST", "WEST"):
        base = f"TLM_BB/swissTLM3D_TLM_BODENBEDECKUNG_{region}"
        files = download_zip_members(
            paths.TLM3D_SHP_URL, [f"{base}.{ext}" for ext in ("shp", "shx", "dbf", "prj")], raw_dir
        )
        gdf = gpd.read_file(files[0], columns=["OBJEKTART"])
        parts.append(gdf[gdf["OBJEKTART"] == "Stehende Gewaesser"])
    water = pd.concat(parts, ignore_index=True)
    water["geometry"] = shapely.make_valid(water.geometry.force_2d().values)
    merged = shapely.union_all(water.geometry.values)
    polys = gpd.GeoDataFrame(geometry=[merged], crs=paths.CRS).explode(ignore_index=True)
    polys = polys[polys.area >= paths.MIN_LAKE_AREA].reset_index(drop=True)
    polys.to_file(path, driver="GPKG")
    return polys


def fill_population_gaps(population: pd.DataFrame, municipality_ids: pd.Series) -> pd.DataFrame:
    """Ergänzt fehlende Bevölkerungszahlen aus swissBOUNDARIES3D 2023-01.

    Die BFS-Tabelle 2021 kennt Gemeinden noch nicht, die 2022/2023 fusioniert haben
    (z. B. Andelfingen, Böztal, Zurzach). Für diese wird die Einwohnerzahl aus
    swissBOUNDARIES3D übernommen (Abweichung zu BFS 2021 sonst im Median ~1 %).
    """
    official = official_municipalities().set_index("bfs_nummer")["einwohnerzahl"]
    pop = pd.DataFrame({"BFSNR": municipality_ids}).merge(population, on="BFSNR", how="left")
    if "SOURCE" not in pop:
        pop["SOURCE"] = pd.NA
    pop.loc[pop["POP_TOTAL"].notna() & pop["SOURCE"].isna(), "SOURCE"] = "BFS 2021"
    missing = pop["POP_TOTAL"].isna()
    pop.loc[missing, "POP_TOTAL"] = pop.loc[missing, "BFSNR"].map(official)
    pop.loc[missing, "SOURCE"] = "swissBOUNDARIES3D 2023-01"
    pop["POP_TOTAL"] = pop["POP_TOTAL"].astype(int)
    return pop[["BFSNR", "POP_TOTAL", "SOURCE"]]


# --------------------------------------------------------------------------
# Ausführen
# --------------------------------------------------------------------------
def main(interim_dir: Path = paths.INTERIM_DIR) -> None:
    """Erzeugt die Zwischenstände, soweit die Rohdaten verfügbar sind."""
    interim_dir = Path(interim_dir)
    interim_dir.mkdir(parents=True, exist_ok=True)

    def write(gdf: gpd.GeoDataFrame, name: str) -> None:
        out = interim_dir / name
        if out.exists():
            out.unlink()
        gdf.to_file(out, driver="GeoJSON")
        print(f"Geschrieben: {out} ({len(gdf)} Objekte)")

    # 1) Abstimmungsresultate + Geometrien (data.zip)
    if paths.RAW_BFS_SHP.exists() and paths.RAW_RESULTS_XLSX.exists():
        write(results_with_geometries(), paths.INTERIM_RESULTS.name)
    else:
        print("Übersprungen: results_bfs (Rohdaten aus data.zip fehlen)")

    # 2) Velounfälle (öffentlich, wird heruntergeladen)
    write(bicycle_accidents(), paths.INTERIM_ACCIDENTS.name)

    # 3) Velowege (data.zip)
    if paths.RAW_OSM_ROADS_SHP.exists() and paths.RAW_VELOLAND_SHP.exists():
        write(bike_network(), paths.INTERIM_BIKES.name)
    else:
        print("Übersprungen: bikes (Rohdaten aus data.zip fehlen)")

    # 4) Bevölkerung: BFS 2021 (data.zip) bzw. versionierte Tabelle, Lücken ergänzen
    out = interim_dir / paths.INTERIM_POPULATION.name
    if paths.RAW_POPULATION_CSV.exists():
        population = population_from_raw()
    else:
        population = pd.read_csv(out)
        population = (
            population[population["SOURCE"].ne("swissBOUNDARIES3D 2023-01")]
            if "SOURCE" in population
            else population
        )
        population = population.dropna(subset=["POP_TOTAL"])
    ids = gpd.read_file(interim_dir / paths.INTERIM_RESULTS.name, columns=["GMDNR"])["GMDNR"]
    fill_population_gaps(population, ids).to_csv(out, index=False)
    print(f"Geschrieben: {out}")
    print("Hinweis: street_lengths_qgis.csv stammt aus einem manuellen QGIS-Schritt.")
