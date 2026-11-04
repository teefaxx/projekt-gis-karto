"""Zwischenstände (data/interim/) -> Endresultat (data/processed/).

Ersetzt die frühere Kette count_accidents.py -> add_bike.py -> add_population.py
-> (ArcGIS/QGIS) -> map_values.py / correlation.py. Alles geschieht im Speicher; es
werden nur die beiden Endprodukte geschrieben:

    final_values.geojson   Kennwerte und Klassierung pro Gemeinde
    canton_accidents.csv   Velounfälle pro 100'000 EW pro Kanton
"""

from __future__ import annotations

import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import paths

# Spaltennamen in results_bfs.geojson -> Namen im Endresultat
RESULT_COLUMNS = {
    "GMDNR": "BFSNR",
    "GMDNAME_y": "GMDNAME",  # offizieller Name aus den BFS-Geometrien
    "Ja in %": "YES_IN_PER",
    "BZNR": "BZNR",
    "KTNR": "KTNR",
    "E_CNTR": "E_CNTR",
    "N_CNTR": "N_CNTR",
    "geometry": "geometry",
}


# --------------------------------------------------------------------------
# Laden
# --------------------------------------------------------------------------
def load_municipalities(path: Path = paths.INTERIM_RESULTS) -> gpd.GeoDataFrame:
    """Gemeinden mit Abstimmungsresultat und Geometrie (EPSG:2056)."""
    gdf = gpd.read_file(path, columns=[c for c in RESULT_COLUMNS if c != "geometry"])
    gdf = gdf[list(RESULT_COLUMNS)].rename(columns=RESULT_COLUMNS)
    return gdf.to_crs(paths.CRS)


def compute_bike_lengths(
    municipalities: gpd.GeoDataFrame, bikes_path: Path = paths.INTERIM_BIKES
) -> pd.DataFrame:
    """Velowege an den Gemeindegrenzen schneiden und die Länge pro Gemeinde summieren.

    Ersetzt den früheren manuellen ArcGIS-Schritt. Die Resultate stimmen in 1722
    Gemeinden bis ~1e-8 (relativ) mit ArcGIS überein. In Genf hatte ArcGIS 9 Gemeinden
    ganz ausgelassen und in 3 weiteren nur einen Teil der Velowege gezählt
    (z. B. 6638 Satigny: 0.7 statt 15.3 km).
    """
    bikes = gpd.read_file(bikes_path, columns=[]).to_crs(paths.CRS)
    pieces = gpd.overlay(
        bikes, municipalities[["BFSNR", "geometry"]], how="intersection", keep_geom_type=True
    )
    pieces["length"] = pieces.geometry.length
    return pieces.groupby("BFSNR")["length"].sum().rename("BIKE_LENGTH").reset_index()


def load_street_lengths(path: Path = paths.INTERIM_STREET_LENGTHS) -> pd.DataFrame:
    """Länge des Strassennetzes pro Gemeinde aus dem QGIS-Schritt."""
    df = pd.read_csv(path)[["BFSNR", "LENGTH"]]
    return df.rename(columns={"LENGTH": "STREET_LENGTH"})


def load_population(path: Path = paths.INTERIM_POPULATION) -> pd.DataFrame:
    """Ständige Wohnbevölkerung pro Gemeinde (BFS 2021, Fusionen aus swissBOUNDARIES3D)."""
    return pd.read_csv(path)[["BFSNR", "POP_TOTAL"]]


# --------------------------------------------------------------------------
# Berechnungen
# --------------------------------------------------------------------------
def count_accidents(
    municipalities: gpd.GeoDataFrame, accidents_path: Path = paths.INTERIM_ACCIDENTS
) -> pd.Series:
    """Anzahl Velounfälle pro Gemeinde (Punkt im Inneren des Polygons)."""
    accidents = gpd.read_file(accidents_path, columns=[]).to_crs(paths.CRS)
    joined = gpd.sjoin(
        municipalities[["BFSNR", "geometry"]], accidents, how="inner", predicate="contains"
    )
    counts = joined.groupby("BFSNR").size()
    return municipalities["BFSNR"].map(counts).fillna(0).astype(int).rename("ACCIDENTS")


def classify(yes: pd.Series, bike: pd.Series, bike_threshold: float) -> pd.Series:
    """Bivariate Klassierung (Werte als Dezimalzahlen).

         2  viel Velowege, viele Ja      1  viel Velowege, wenige Ja
         0  wenig Velowege, viele Ja    -1  wenig Velowege, wenige Ja
       NaN  keine Daten (kein eigenes Abstimmungsresultat oder kein Strassennetz-Wert)

    Ja-Schwelle = gerundeter Mittelwert der Gemeinden mit eigenem Resultat.
    """
    yes_threshold = round(float(yes.mean()), paths.YES_THRESHOLD_DECIMALS)
    good_bike = bike >= bike_threshold
    many_yes = yes >= yes_threshold
    value = np.select(
        [good_bike & many_yes, good_bike & ~many_yes, ~good_bike & many_yes],
        [2.0, 1.0, 0.0],
        default=-1.0,
    )
    value = np.where(yes.isna() | bike.isna(), np.nan, value)
    return pd.Series(value, index=yes.index, name="VALUE")


def build_final(interim_dir: Path = paths.INTERIM_DIR) -> gpd.GeoDataFrame:
    """Berechnet final_values im Speicher (eine Zeile pro Gemeinde, 2136)."""
    interim_dir = Path(interim_dir)
    gdf = load_municipalities(interim_dir / paths.INTERIM_RESULTS.name)
    gdf["ACCIDENTS"] = count_accidents(gdf, interim_dir / paths.INTERIM_ACCIDENTS.name)

    bike_lengths = compute_bike_lengths(gdf, interim_dir / paths.INTERIM_BIKES.name)
    gdf = gdf.merge(bike_lengths, on="BFSNR", how="left")
    gdf["BIKE_LENGTH"] = gdf["BIKE_LENGTH"].fillna(0.0)  # keine Velowege im Gemeindegebiet
    gdf = gdf.merge(
        load_street_lengths(interim_dir / paths.INTERIM_STREET_LENGTHS.name),
        on="BFSNR",
        how="left",  # BFS 389 Meienried hat keinen Strassennetz-Wert -> keine Daten
    )
    gdf = gdf.merge(
        load_population(interim_dir / paths.INTERIM_POPULATION.name), on="BFSNR", how="left"
    )

    # '...' = kein eigenes Resultat (gemeinsame Urne) -> fehlender Wert, nicht 0
    gdf["YES_IN_PER"] = pd.to_numeric(gdf["YES_IN_PER"], errors="coerce") / 100
    gdf["BIKE_STREET_PER"] = gdf["BIKE_LENGTH"] / gdf["STREET_LENGTH"]

    pop = gdf["POP_TOTAL"].where(gdf["POP_TOTAL"] > 0)
    gdf["ACCIDENTS_PER_100K"] = gdf["ACCIDENTS"] / pop * 100_000

    gdf["VALUE"] = classify(gdf["YES_IN_PER"], gdf["BIKE_STREET_PER"], paths.BIKE_THRESHOLD)
    return gdf[paths.FINAL_COLUMNS]


def canton_accidents(final: pd.DataFrame) -> pd.DataFrame:
    """Velounfälle pro 100'000 EW pro Kanton = Summe Unfälle / Summe Einwohner.

    (Die ursprüngliche Version mittelte die Gemeinderaten ungewichtet; dabei zählte
    eine Gemeinde mit 50 Einwohnern gleich viel wie die Stadt Zürich.)
    """
    df = final.groupby("KTNR")[["ACCIDENTS", "POP_TOTAL"]].sum().reset_index()
    df["ACCIDENTS_PER_100K"] = (df["ACCIDENTS"] / df["POP_TOTAL"] * 100_000).round(2)
    return df


def main(
    output_dir: Path = paths.PROCESSED_DIR, interim_dir: Path = paths.INTERIM_DIR
) -> gpd.GeoDataFrame:
    """Berechnet und schreibt final_values.geojson und canton_accidents.csv."""
    start = time.perf_counter()
    final = build_final(interim_dir)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / paths.FINAL_VALUES_NAME
    canton_path = output_dir / paths.CANTON_ACCIDENTS_NAME
    if final_path.exists():
        final_path.unlink()
    final.to_file(final_path, driver="GeoJSON")
    canton_accidents(final).to_csv(canton_path, index=False)

    print(f"Geschrieben: {final_path} ({len(final)} Gemeinden)")
    print(f"Geschrieben: {canton_path}")
    print(f"Build-Dauer: {time.perf_counter() - start:.1f} s")
    return final
