"""Rohdaten (data/raw/) -> Zwischenstände (data/interim/).

Portierung von src/get_data/{results_data,accidents_data,bike_data}.py und
src/add_population.py (read_pop_new). Die Rohdaten sind nicht im Repo; der
ursprüngliche Download-Link ist abgelaufen. Die Zwischenstände in data/interim/
sind versioniert, `python -m pipeline build` braucht diese Schritte also nicht.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

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


def bicycle_accidents(path: Path = paths.RAW_ACCIDENTS_JSON) -> gpd.GeoDataFrame:
    """Unfälle mit Velobeteiligung als Punkte in LV95.

    Filter: Monat <= 9 und Jahr <= 2018 (siehe Kommentar in paths.py).
    """
    require_raw(path)
    raw = gpd.read_file(path)
    df = pd.DataFrame(raw[ACCIDENT_COLUMNS])

    to_bool = {"true": True, "false": False}
    df["AccidentInvolvingBicycle"] = df["AccidentInvolvingBicycle"].str.lower().map(to_bool)
    df["AccidentInvolvingPedestrian"] = df["AccidentInvolvingPedestrian"].str.lower().map(to_bool)
    int_cols = [
        "AccidentYear",
        "AccidentMonth",
        "AccidentLocation_CHLV95_E",
        "AccidentLocation_CHLV95_N",
    ]
    df[int_cols] = df[int_cols].astype(int)

    mask = (
        (df["AccidentMonth"] <= paths.ACCIDENT_MAX_MONTH)
        & (df["AccidentYear"] <= paths.ACCIDENT_MAX_YEAR)
        & df["AccidentInvolvingBicycle"].astype(bool)
    )
    df = df.loc[mask]

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


# --------------------------------------------------------------------------
# Ausführen
# --------------------------------------------------------------------------
def main(interim_dir: Path = paths.INTERIM_DIR) -> None:
    """Erzeugt alle Zwischenstände aus den Rohdaten."""
    require_raw(
        paths.RAW_BFS_SHP,
        paths.RAW_RESULTS_XLSX,
        paths.RAW_ACCIDENTS_JSON,
        paths.RAW_OSM_ROADS_SHP,
        paths.RAW_VELOLAND_SHP,
        paths.RAW_POPULATION_CSV,
    )
    interim_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        paths.INTERIM_RESULTS.name: results_with_geometries,
        paths.INTERIM_ACCIDENTS.name: bicycle_accidents,
        paths.INTERIM_BIKES.name: bike_network,
    }
    for name, func in targets.items():
        out = interim_dir / name
        func().to_file(out, driver="GeoJSON")
        print(f"Geschrieben: {out}")

    out = interim_dir / paths.INTERIM_POPULATION.name
    population_from_raw().to_csv(out, index=False)
    print(f"Geschrieben: {out}")
    print(
        "Hinweis: bike_lengths_arcgis.csv und street_lengths_qgis.csv stammen aus manuellen "
        "GIS-Schritten und werden hier nicht erzeugt (siehe build --recompute-bike-lengths)."
    )
