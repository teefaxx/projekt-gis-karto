"""Exportiert die Daten für die interaktive Webkarte (``web/``).

Erzeugt kompakte GeoJSON-Dateien in WGS84 (EPSG:4326):

* ``web/data/gemeinden.geojson`` – Gemeinden mit Klassifikation und Kennzahlen
* ``web/data/kantone.geojson``   – Kantonsgrenzen
* ``web/data/kantone_punkte.geojson`` – Kantonsmittelpunkte mit Velounfällen pro 100'000 EW
* ``web/data/seen.geojson``      – Seen (swisstopo / BFS Generalisierung K4)
* ``web/data/meta.json``         – Schwellenwerte und Metadaten für Legende und Popups

Die Gemeindegrenzen werden mit ``shapely.coverage_simplify`` vereinfacht. Das
vereinfacht gemeinsame Grenzen nur einmal, so entstehen keine Lücken oder
Überlappungen zwischen Nachbargemeinden.

Aufruf::

    python -m pipeline webdata
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline.paths import BIKE_THRESHOLD
from pipeline.paths import INTERIM_DIR as INTERIM
from pipeline.paths import PROCESSED_DIR as PROCESSED
from pipeline.paths import ROOT_DIR as ROOT

QGIS = ROOT / "map" / "QGIS"
WEB_DATA = ROOT / "web" / "data"

WGS84 = "EPSG:4326"
PRECISION = 5  # Dezimalstellen (~1 m), reicht für 1:25'000 und kleiner

NATIONAL_YES = 0.736  # offizielles Schweizer Resultat vom 23.09.2018

# Klassengrenzen der Kreissymbole (wie in der gedruckten Karte)
ACC_BREAKS = [140, 245, 365.1]
ACC_LABELS = ["< 140", "140 – 244", "245 – 365", "> 365"]


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("...", np.nan), errors="coerce")


def _simplify_coverage(gdf: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    """Topologieerhaltende Vereinfachung (Toleranz in Metern, LV95)."""
    out = gdf.copy()
    geoms = shapely.make_valid(out.geometry.values)
    out["geometry"] = shapely.coverage_simplify(geoms, tolerance=tolerance)
    return out


def _write(gdf: gpd.GeoDataFrame, name: str) -> Path:
    path = WEB_DATA / name
    gdf = gdf.to_crs(WGS84)
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, 10**-PRECISION)
    gdf = gdf[~gdf.geometry.is_empty]
    if path.exists():
        path.unlink()
    gdf.to_file(
        path,
        driver="GeoJSON",
        engine="pyogrio",
        layer_options={"COORDINATE_PRECISION": PRECISION, "RFC7946": "YES", "WRITE_NAME": "NO"},
    )
    # Kompakt (ohne Einrückung) neu schreiben – spart ~25 % Dateigrösse
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("xy_coordinate_resolution", None)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1e6:.2f} MB  ({len(gdf)} Features)")
    return path


def municipalities() -> tuple[gpd.GeoDataFrame, dict]:
    final = gpd.read_file(PROCESSED / "final_values.geojson")
    results = gpd.read_file(INTERIM / "results_bfs.geojson", ignore_geometry=True)
    bikes = pd.read_csv(INTERIM / "bike_lengths_arcgis.csv", sep=";")
    streets = pd.read_csv(INTERIM / "street_lengths_qgis.csv")

    votes = pd.DataFrame(
        {
            "BFSNR": results["GMDNR"],
            "name": results["GMDNAME_y"].str.strip(),
            "urne": results["GMDNAME_x"].str.extract(r"Standort: ([^)]*?)\s*\)")[0],
            "stimmberechtigte": _to_number(results["Stimmberechtigte"]),
            "beteiligung": _to_number(results["Beteiligung in %"]),
            "ja": _to_number(results["Ja"]),
            "nein": _to_number(results["Nein"]),
        }
    )

    gdf = (
        final.merge(votes, on="BFSNR", how="left")
        .merge(
            bikes.rename(columns={"BFS": "BFSNR", "SUM_Shape_Length": "bike_m"})[
                ["BFSNR", "bike_m"]
            ],
            on="BFSNR",
            how="left",
        )
        .merge(
            streets.rename(columns={"LENGTH": "street_m"})[["BFSNR", "street_m"]],
            on="BFSNR",
            how="left",
        )
    )

    no_data = gdf["ja"].isna()
    yes_threshold = round(final["YES_IN_PER"].mean(), 2)  # wie in pipeline/build.py

    out = gpd.GeoDataFrame(
        {
            "id": gdf["BFSNR"].astype(int),
            "name": gdf["name"].fillna(gdf["GMDNAME"]),
            "kt": gdf["KTNR"].astype(int),
            # Klasse wie in der gedruckten Karte; Gemeinden ohne eigenes
            # Abstimmungsresultat (gemeinsame Urne) erhalten -9 = keine Daten.
            "cls": np.where(no_data, -9, gdf["VALUE"]).astype(int),
            "yes": (gdf["YES_IN_PER"] * 100).round(2).where(~no_data),
            "bike": (gdf["BIKE_STREET_PER"] * 100).round(2),
            "bike_km": (gdf["bike_m"] / 1000).round(1),
            "street_km": (gdf["street_m"] / 1000).round(1),
            "acc": gdf["ACCIDENTS"].astype(int),
            "acc100k": gdf["ACCIDENTS_PER_100K"].round(1),
            "pop": gdf["POP_TOTAL"].astype("Int64"),
            "voters": gdf["stimmberechtigte"].astype("Int64"),
            "turnout": gdf["beteiligung"].round(1),
            "ja": gdf["ja"].astype("Int64"),
            "nein": gdf["nein"].astype("Int64"),
            "urne": gdf["urne"],
        },
        geometry=gdf.geometry,
        crs=final.crs,
    )
    meta = {
        "yesThreshold": yes_threshold * 100,
        "bikeThreshold": round(BIKE_THRESHOLD * 100, 2),
        "nationalYes": NATIONAL_YES * 100,
        "municipalities": int(len(out)),
        "noData": int(no_data.sum()),
    }
    return out, meta


def cantons() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    poly = gpd.read_file(QGIS / "Kanton" / "K4kant20220101gf_ch2007Poly.shp")
    pts = gpd.read_file(QGIS / "Kanton" / "K4kant20220101gf_ch2007Pnts.shp")
    acc = pd.read_csv(PROCESSED / "canton_accidents.csv")

    poly = gpd.GeoDataFrame(
        {"kt": poly["id"].astype(int), "name": poly["name"]}, geometry=poly.geometry, crs=poly.crs
    )

    pts = pts.merge(acc, left_on="id", right_on="KTNR")
    abbr = pts["Kurz"].where(pts["id"] != 14, "SH")  # Tippfehler im Quell-Shapefile (SG statt SH)
    values = pts["ACCIDENTS_PER_100K"]
    pts = gpd.GeoDataFrame(
        {
            "kt": pts["id"].astype(int),
            "name": pts["name"],
            "abbr": abbr,
            "acc100k": values.round(1),
            "accClass": np.digitize(values, ACC_BREAKS).astype(int),
        },
        geometry=pts.geometry,
        crs=pts.crs,
    )
    return poly, pts


def lakes() -> gpd.GeoDataFrame:
    topo = QGIS / "00_TOPO" / "K4_seenyyyymmdd"
    parts = [gpd.read_file(p) for p in sorted(topo.glob("*Poly.shp"))]
    gdf = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame({"name": gdf["name"]}, geometry=gdf.geometry, crs=parts[0].crs)


def main() -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    print("Exportiere Webkarten-Daten …")

    gem, meta = municipalities()
    _write(_simplify_coverage(gem, tolerance=40), "gemeinden.geojson")

    poly, pts = cantons()
    _write(_simplify_coverage(poly, tolerance=60), "kantone.geojson")
    _write(pts, "kantone_punkte.geojson")

    see = lakes()
    see["geometry"] = see.geometry.simplify(30, preserve_topology=True)
    _write(see, "seen.geojson")

    meta.update(
        {
            "accBreaks": ACC_BREAKS,
            "accLabels": ACC_LABELS,
            "cantonNames": dict(zip(pts["kt"].astype(str), pts["abbr"], strict=True)),
            "generated": date.today().isoformat(),
        }
    )
    (WEB_DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(
        f"  web/data/meta.json  (Ja-Schwelle {meta['yesThreshold']:.0f} %, "
        f"Velo-Schwelle {meta['bikeThreshold']:.2f} %)"
    )


if __name__ == "__main__":
    main()
