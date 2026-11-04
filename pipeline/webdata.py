"""Exportiert die Daten für die interaktive Webkarte (``web/``).

Gemeindegrenzen: offizielle Hoheitsgebiete aus swissBOUNDARIES3D (swisstopo, Stand
1.1.2023), als Vektorkacheln (Mapbox Vector Tiles) für die Zoomstufen 5–12. Pro
Zoomstufe wird mit ``shapely.coverage_simplify`` vereinfacht. Gemeinsame Grenzen
werden dabei nur einmal vereinfacht, so entstehen keine Lücken zwischen Gemeinden.
In Zoom 12 entspricht die Geometrie den Originaldaten (Auflösung ~1.6 m).

Die Seen (swissTLM3D) werden aus den Gemeindeflächen ausgeschnitten und zusammen mit
ihnen vereinfacht. So bleibt über einer Basiskarte der See frei, und ohne Basiskarte
schliesst die Seefläche lückenlos an die Gemeinden an.
Die Karte vergrössert ab Zoom 12 die Kacheln weiter.

Ausgabe in ``web/data/``:

* ``tiles/{z}/{x}/{y}.pbf``  Layer ``gemeinden`` (Flächen ohne Seen), ``seen`` (Seeflächen
                             aus swissTLM3D), ``kantone`` (Grenzlinien), ``kantone_flaechen``,
                             ``labels`` (Namenspunkte)
* ``gemeinden.json``         Kennzahlen und Ausdehnung (bbox) pro Gemeinde
* ``kantone.json``           Kennzahlen pro Kanton (Abstimmung, Velowege, Unfälle)
* ``kantone_punkte.geojson`` Kantonssymbole mit Velounfällen pro 100'000 EW
* ``meta.json``              Schwellenwerte, Klassengrenzen, Metadaten

Aufruf::

    python -m pipeline webdata
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from mapbox_vector_tile import decode, encode
from mapbox_vector_tile.encoder import on_invalid_geometry_make_valid

from pipeline import prepare
from pipeline.paths import (
    BIKE_THRESHOLD,
    CANTON_ACCIDENTS,
    FINAL_VALUES,
    INTERIM_POPULATION,
    INTERIM_RESULTS,
    ROOT_DIR,
    YES_THRESHOLD_DECIMALS,
)

WEB_DATA = ROOT_DIR / "web" / "data"
TILES_DIR = WEB_DATA / "tiles"
CANTON_POINTS = ROOT_DIR / "map" / "QGIS" / "Kanton" / "K4kant20220101gf_ch2007Pnts.shp"

MIN_ZOOM, MAX_ZOOM = 5, 12
LABEL_MIN_ZOOM = 9
EXTENT = 4096  # Koordinatenraster pro Kachel
BUFFER = 64  # Puffer in Kachel-Einheiten, verhindert sichtbare Schnittkanten
WEB_MERCATOR_HALF = 20037508.342789244

NATIONAL_YES = 73.6  # offizielles Schweizer Resultat vom 23.09.2018 in %

# Klassencodes für Flächen ohne Klassierung
CLS_NO_DATA = -9  # Gemeinde ohne eigenes Resultat (gemeinsame Urne)
CLS_KOMMUNANZ = -8  # Kommunanz / Staatswald: kein Gemeindegebiet
CLS_LAKE = -7  # kantonale Seefläche (keiner Gemeinde zugeteilt)


# --------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------
def _num(value, digits: int | None = None):
    """JSON-taugliche Zahl (NaN -> None)."""
    if value is None or pd.isna(value):
        return None
    if digits is None:
        return int(value)
    return round(float(value), digits)


def load_areas() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Offizielle Flächen (LV95) mit Klasse, sowie Attributtabelle der Gemeinden."""
    final = gpd.read_file(FINAL_VALUES, ignore_geometry=True)
    results = gpd.read_file(INTERIM_RESULTS, ignore_geometry=True)
    votes = pd.DataFrame(
        {
            "BFSNR": results["GMDNR"],
            "urne": results["GMDNAME_x"].str.extract(r"Standort: ([^)]*?)\s*\)")[0],
            "voters": pd.to_numeric(results["Stimmberechtigte"], errors="coerce"),
            "cast": pd.to_numeric(results["Abgegebene Stimmen"], errors="coerce"),
            "turnout": pd.to_numeric(results["Beteiligung in %"], errors="coerce"),
            "ja": pd.to_numeric(results["Ja"], errors="coerce"),
            "nein": pd.to_numeric(results["Nein"], errors="coerce"),
        }
    )
    attrs = final.merge(votes, on="BFSNR", how="left")

    official = prepare.official_municipalities()
    areas = official.merge(
        attrs[["BFSNR", "VALUE", "GMDNAME"]], left_on="bfs_nummer", right_on="BFSNR", how="left"
    )
    is_lake = areas["name"].str.contains("see|lac", case=False)
    cls = areas["VALUE"].fillna(CLS_NO_DATA)
    cls = cls.where(areas["objektart"] == "Gemeindegebiet", CLS_KOMMUNANZ)
    cls = cls.where(~((areas["objektart"] == "Kantonsgebiet") & is_lake), CLS_LAKE)
    areas = gpd.GeoDataFrame(
        {
            "id": areas["bfs_nummer"].astype(int),
            "name": areas["GMDNAME"].fillna(areas["name"]),
            "kt": areas["kantonsnummer"].astype(int),
            "cls": cls.astype(int),
        },
        geometry=areas.geometry,
        crs=official.crs,
    )
    return areas, attrs


def attribute_table(attrs: pd.DataFrame, areas: gpd.GeoDataFrame) -> list[dict]:
    """Kennzahlen pro Gemeinde (und Kommunanz) inkl. Ausdehnung in WGS84."""
    bounds = areas.to_crs("EPSG:4326").set_index("id").bounds.round(5)
    attrs = attrs.set_index("BFSNR")
    pop_source = pd.read_csv(INTERIM_POPULATION).set_index("BFSNR")["SOURCE"]
    rows = []
    for a in areas.itertuples():
        if a.cls == CLS_LAKE:
            continue
        b = bounds.loc[a.id]
        row = {
            "id": int(a.id),
            "name": a.name,
            "kt": int(a.kt),
            "cls": int(a.cls),
            "bbox": [b.minx, b.miny, b.maxx, b.maxy],
        }
        if a.id in attrs.index:
            r = attrs.loc[a.id]
            row.update(
                yes=_num(r["YES_IN_PER"] * 100, 2),
                bike=_num(r["BIKE_STREET_PER"] * 100, 2),
                bike_km=_num(r["BIKE_LENGTH"] / 1000, 1),
                street_km=_num(r["STREET_LENGTH"] / 1000, 1),
                acc=_num(r["ACCIDENTS"]),
                acc100k=_num(r["ACCIDENTS_PER_100K"], 1),
                pop=_num(r["POP_TOTAL"]),
                voters=_num(r["voters"]),
                turnout=_num(r["turnout"], 1),
                ja=_num(r["ja"]),
                nein=_num(r["nein"]),
                urne=None if pd.isna(r["urne"]) else r["urne"],
                pop_src="swissBOUNDARIES3D"
                if str(pop_source.get(a.id, "")).startswith("swissBOUNDARIES3D")
                else "BFS",
            )
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Kantone: Natural Breaks (Fisher-Jenks) für die Kreisgrössen
# --------------------------------------------------------------------------
def jenks_breaks(values: list[float], k: int) -> list[float]:
    """Optimale Klassengrenzen (minimale Varianz innerhalb der Klassen).

    Gibt die k-1 oberen Grenzen der unteren Klassen zurück (Wert gehört zur Klasse,
    wenn ``value <= grenze``).
    """
    x = sorted(values)
    n = len(x)
    cost = [[0.0] * n for _ in range(n)]
    for i in range(n):
        s = s2 = 0.0
        for j in range(i, n):
            s += x[j]
            s2 += x[j] ** 2
            cost[i][j] = s2 - s * s / (j - i + 1)
    best = [[math.inf] * n for _ in range(k)]
    split = [[0] * n for _ in range(k)]
    for j in range(n):
        best[0][j] = cost[0][j]
    for c in range(1, k):
        for j in range(c, n):
            for i in range(c, j + 1):
                v = best[c - 1][i - 1] + cost[i][j]
                if v < best[c][j]:
                    best[c][j], split[c][j] = v, i
    bounds, j = [], n - 1
    for c in range(k - 1, 0, -1):
        i = split[c][j]
        bounds.append(x[i - 1])
        j = i - 1
    return sorted(bounds)


def canton_points() -> tuple[gpd.GeoDataFrame, list[str]]:
    """Kantonssymbole (Lage wie in der gedruckten Karte) mit Unfallrate und Klasse."""
    pts = gpd.read_file(CANTON_POINTS)
    acc = pd.read_csv(CANTON_ACCIDENTS)
    pts = pts.merge(acc, left_on="id", right_on="KTNR")
    abbr = pts["Kurz"].where(pts["id"] != 14, "SH")  # Tippfehler im Quell-Shapefile
    values = pts["ACCIDENTS_PER_100K"]
    breaks = jenks_breaks(values.tolist(), 4)
    acc_class = np.searchsorted(breaks, values, side="left")

    labels = []
    for c in range(4):
        members = values[acc_class == c]
        labels.append(f"{members.min():.0f} – {members.max():.0f}")

    gdf = gpd.GeoDataFrame(
        {
            "kt": pts["id"].astype(int),
            "name": pts["name"],
            "abbr": abbr,
            "acc": pts["ACCIDENTS"].astype(int),
            "pop": pts["POP_TOTAL"].astype(int),
            "acc100k": values.round(1),
            "accClass": acc_class.astype(int),
        },
        geometry=pts.geometry,
        crs=pts.crs,
    )
    return gdf, labels


def canton_table(attrs: pd.DataFrame, areas: gpd.GeoDataFrame, pts: gpd.GeoDataFrame) -> list:
    """Kennzahlen pro Kanton, aus den Gemeindewerten summiert.

    Ja-Anteil = Summe Ja / (Summe Ja + Nein), entspricht dem offiziellen Kantonsresultat
    (Gemeinden mit gemeinsamer Urne sind in der Standortgemeinde enthalten).
    """
    bounds = areas[areas["cls"] != CLS_LAKE].dissolve("kt").to_crs("EPSG:4326").bounds.round(4)
    a = attrs.copy()
    a["cls"] = a["VALUE"].fillna(CLS_NO_DATA).astype(int)
    rows = []
    for p in pts.sort_values("acc100k", ascending=False).itertuples():
        g = a[a["KTNR"] == p.kt]
        ja, nein = g["ja"].sum(), g["nein"].sum()
        b = bounds.loc[p.kt]
        rows.append(
            {
                "id": int(p.kt),
                "name": p.name,
                "abbr": p.abbr,
                "bbox": [b.minx, b.miny, b.maxx, b.maxy],
                "yes": round(ja / (ja + nein) * 100, 2),
                "ja": int(ja),
                "nein": int(nein),
                "turnout": round(g["cast"].sum() / g["voters"].sum() * 100, 1),
                "bike": round(g["BIKE_LENGTH"].sum() / g["STREET_LENGTH"].sum() * 100, 2),
                "bike_km": round(g["BIKE_LENGTH"].sum() / 1000, 1),
                "street_km": round(g["STREET_LENGTH"].sum() / 1000, 1),
                "acc": int(p.acc),
                "pop": int(p.pop),
                "acc100k": float(p.acc100k),
                "accClass": int(p.accClass),
                "rank": len(rows) + 1,
                "municipalities": int(len(g)),
                "classes": {str(k): int(v) for k, v in g["cls"].value_counts().items()},
            }
        )
    return rows


# --------------------------------------------------------------------------
# Vektorkacheln
# --------------------------------------------------------------------------
def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = 2 * WEB_MERCATOR_HALF / 2**z
    minx = -WEB_MERCATOR_HALF + x * size
    maxy = WEB_MERCATOR_HALF - y * size
    return minx, maxy - size, minx + size, maxy


def _tile_range(bounds: np.ndarray, z: int) -> tuple[range, range]:
    size = 2 * WEB_MERCATOR_HALF / 2**z
    minx, miny, maxx, maxy = bounds
    xs = range(int((minx + WEB_MERCATOR_HALF) // size), int((maxx + WEB_MERCATOR_HALF) // size) + 1)
    ys = range(int((WEB_MERCATOR_HALF - maxy) // size), int((WEB_MERCATOR_HALF - miny) // size) + 1)
    return xs, ys


def _tolerance(z: int) -> float:
    """Vereinfachungstoleranz in Web-Mercator-Metern: ~1/2 Pixel einer 512er-Kachel."""
    if z >= MAX_ZOOM:
        return 1.0
    return 0.5 * 2 * WEB_MERCATOR_HALF / (512 * 2**z)


def _to_tile(geom, tile):
    """In Kachelkoordinaten (0..EXTENT, y nach oben) umrechnen und auf ganze Zahlen runden.

    Das Runden erledigen wir selbst und reparieren danach die Geometrie: Der Encoder
    würde Flächen, die durch das Runden ungültig werden, sonst stillschweigend verwerfen.
    """
    minx, miny, maxx, maxy = tile
    scale = np.array([EXTENT / (maxx - minx), EXTENT / (maxy - miny)])
    offset = np.array([minx, miny])
    g = shapely.transform(geom, lambda xy: (xy - offset) * scale)
    g = shapely.set_precision(g, 1.0)
    if g.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
        g = _polygonal(np.array([g]))[0]
    return g


def _layer(name, geoms, props, ids, tree, rect, tile):
    features = []
    for i in tree.query(shapely.box(*rect)):
        g = _to_tile(shapely.clip_by_rect(geoms[i], *rect), tile)
        if not g.is_empty:
            features.append({"geometry": g, "properties": props[i], "id": ids[i]})
    return {"name": name, "features": features} if features else None


def _polygonal(geoms: np.ndarray) -> np.ndarray:
    """Gültige (Multi-)Polygone; Linien/Punkte aus make_valid werden verworfen."""
    out = shapely.make_valid(geoms)
    for i, g in enumerate(out):
        if g.geom_type == "GeometryCollection":
            polys = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
            out[i] = shapely.union_all(polys) if polys else shapely.Polygon()
    return out


GRID = 0.01  # gemeinsames Koordinatenraster (m), damit Nachbarflächen exakt aufeinanderpassen


def _cut_lakes(geoms: np.ndarray, lakes: np.ndarray) -> np.ndarray:
    """Gemeindeflächen ohne Seen (Differenz nur dort, wo sich beide schneiden)."""
    geoms = geoms.copy()
    lake_union = shapely.union_all(lakes, grid_size=GRID)
    shapely.prepare(lake_union)
    hit = shapely.intersects(geoms, lake_union)
    geoms[hit] = shapely.difference(geoms[hit], lake_union, grid_size=GRID)
    return geoms


def write_tiles(areas: gpd.GeoDataFrame, lakes: gpd.GeoDataFrame) -> int:
    merc = areas.to_crs("EPSG:3857")
    lakes_m = lakes.to_crs("EPSG:3857")
    # Alle Flächen auf dasselbe Raster setzen, sonst entstehen Lücken zwischen Nachbarn
    uncut = _polygonal(shapely.set_precision(merc.geometry.values, GRID))
    lake_geoms = _polygonal(shapely.set_precision(lakes_m.geometry.values, GRID))
    cut = _polygonal(_cut_lakes(uncut, lake_geoms))
    keep = ~shapely.is_empty(cut)
    n_areas = int(keep.sum())
    # Gemeinden (ohne Seen) und Seen bilden zusammen eine lückenlose Abdeckung
    # Seeteile ausserhalb der Schweiz und Überlappungen mit Gemeinden ausschliessen
    lake_geoms = shapely.intersection(
        lake_geoms, shapely.union_all(uncut, grid_size=GRID), grid_size=GRID
    )
    lake_geoms = _polygonal(lake_geoms)
    coverage = np.concatenate([cut[keep], lake_geoms])
    kts = merc["kt"].to_numpy()

    props = [
        {"id": int(r.id), "cls": int(r.cls), "kt": int(r.kt)}
        for r, k in zip(merc.itertuples(), keep, strict=True)
        if k
    ]
    ids = [p["id"] for p in props]
    lake_props = [{"see": 1}] * len(lakes_m)
    lake_ids = list(range(1, len(lakes_m) + 1))

    label_mask = merc["cls"].to_numpy() != CLS_LAKE
    lbl_geoms = shapely.point_on_surface(uncut)[label_mask]
    lbl_props = [{"id": int(r.id), "name": r.name} for r in merc[label_mask].itertuples()]
    lbl_ids = [int(i) for i in merc.loc[label_mask, "id"]]
    lbl_tree = shapely.STRtree(lbl_geoms)

    if TILES_DIR.exists():
        shutil.rmtree(TILES_DIR)
    count = 0
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        tol = _tolerance(z)
        simple = _polygonal(shapely.coverage_simplify(coverage, tolerance=tol))
        gem, see = simple[:n_areas], simple[n_areas:]
        gem_tree, see_tree = shapely.STRtree(gem), shapely.STRtree(see)

        # Kantone aus den nicht beschnittenen Gemeinden (Grenzen laufen durch die Seen)
        full = _polygonal(shapely.coverage_simplify(uncut, tolerance=tol))
        cantons = gpd.GeoDataFrame({"kt": kts}, geometry=full, crs="EPSG:3857").dissolve("kt")
        canton_polys = cantons.geometry.values
        canton_lines = shapely.boundary(canton_polys)
        canton_props = [{"kt": int(k)} for k in cantons.index]
        canton_ids = [int(k) for k in cantons.index]
        cpoly_tree, cline_tree = shapely.STRtree(canton_polys), shapely.STRtree(canton_lines)

        xs, ys = _tile_range(shapely.total_bounds(full), z)
        for x in xs:
            for y in ys:
                tile = _tile_bounds(z, x, y)
                pad = (tile[2] - tile[0]) * BUFFER / EXTENT
                rect = (tile[0] - pad, tile[1] - pad, tile[2] + pad, tile[3] + pad)
                layers = [
                    _layer("gemeinden", gem, props, ids, gem_tree, rect, tile),
                    _layer("seen", see, lake_props, lake_ids, see_tree, rect, tile),
                    _layer(
                        "kantone_flaechen",
                        canton_polys,
                        canton_props,
                        canton_ids,
                        cpoly_tree,
                        rect,
                        tile,
                    ),
                    _layer(
                        "kantone", canton_lines, canton_props, canton_ids, cline_tree, rect, tile
                    ),
                ]
                if z >= LABEL_MIN_ZOOM:
                    layers.append(
                        _layer("labels", lbl_geoms, lbl_props, lbl_ids, lbl_tree, tile, tile)
                    )
                layers = [layer for layer in layers if layer]
                if not any(layer["name"] in ("gemeinden", "kantone_flaechen") for layer in layers):
                    continue
                data = encode(
                    layers,
                    default_options={
                        "extents": EXTENT,
                        "y_coord_down": False,
                        "on_invalid_geometry": on_invalid_geometry_make_valid,
                    },
                )
                # Kontrolle: Der Encoder darf keine Fläche verwerfen
                decoded = decode(data)
                for layer in layers:
                    kept = len(decoded.get(layer["name"], {}).get("features", []))
                    if kept != len(layer["features"]):
                        raise RuntimeError(
                            f"Kachel {z}/{x}/{y}: {len(layer['features']) - kept} Objekte im "
                            f"Layer {layer['name']} verworfen"
                        )
                out = TILES_DIR / str(z) / str(x) / f"{y}.pbf"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                count += 1
        print(f"  Zoom {z:2d}: Toleranz {tol:7.1f} m")
    return count


# --------------------------------------------------------------------------
# Ausführen
# --------------------------------------------------------------------------
def _write_json(name: str, data) -> None:
    path = WEB_DATA / name
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  web/data/{name}  {path.stat().st_size / 1e3:.0f} kB")


def main() -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    print("Exportiere Webkarten-Daten …")
    for old in ("gemeinden.geojson", "kantone.geojson", "seen.geojson"):
        (WEB_DATA / old).unlink(missing_ok=True)

    areas, attrs = load_areas()
    lakes = prepare.lakes()
    n = write_tiles(areas, lakes)
    size = sum(p.stat().st_size for p in TILES_DIR.rglob("*.pbf"))
    print(f"  web/data/tiles  {n} Kacheln, {size / 1e6:.1f} MB")

    _write_json("gemeinden.json", attribute_table(attrs, areas))

    pts, acc_labels = canton_points()
    pts_path = WEB_DATA / "kantone_punkte.geojson"
    pts_path.write_text(pts.to_crs("EPSG:4326").to_json(drop_id=True), encoding="utf-8")
    _write_json("kantone.json", canton_table(attrs, areas, pts))

    valid_yes = attrs["YES_IN_PER"].dropna()
    meta = {
        "yesThreshold": round(round(valid_yes.mean(), YES_THRESHOLD_DECIMALS) * 100, 2),
        "bikeThreshold": round(BIKE_THRESHOLD * 100, 2),
        "nationalYes": NATIONAL_YES,
        "accLabels": acc_labels,
        "accidentPeriod": "Januar 2011 – September 2018",
        "cantonNames": dict(zip(pts["kt"].astype(str), pts["abbr"], strict=True)),
        "maxTileZoom": MAX_ZOOM,
        "generated": date.today().isoformat(),
    }
    _write_json("meta.json", meta)


if __name__ == "__main__":
    main()
