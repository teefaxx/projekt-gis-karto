"""Zwischenstände (data/interim/) -> Endresultat (data/processed/).

Ersetzt die frühere Kette count_accidents.py -> add_bike.py -> add_population.py
-> (QGIS) -> map_values.py / correlation.py. Alles geschieht im Speicher; es werden
nur die beiden Endprodukte geschrieben:

    final_values.geojson   Kennwerte und Klassierung pro Gemeinde
    canton_accidents.csv   Mittelwert der Velounfälle pro 100'000 EW pro Kanton
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
    "GMDNAME_x": "GMDNAME",  # Name aus dem Abstimmungs-Excel (wie bisher)
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


def load_bike_lengths(path: Path = paths.INTERIM_BIKE_LENGTHS) -> pd.DataFrame:
    """Summierte Veloweglänge pro Gemeinde aus dem ArcGIS-Schritt."""
    df = pd.read_csv(path, sep=";")
    return df.rename(
        columns={"BFS": "BFSNR", "FREQUENCY": "SUM_FREQ", "SUM_Shape_Length": "SUM_LENGTH"}
    )[["BFSNR", "SUM_FREQ", "SUM_LENGTH"]]


def compute_bike_lengths(
    municipalities: gpd.GeoDataFrame, bikes_path: Path = paths.INTERIM_BIKES
) -> pd.DataFrame:
    """Ersetzt den ArcGIS-Schritt: Velowege an Gemeindegrenzen schneiden und summieren.

    Stimmt mit bike_lengths_arcgis.csv bis ~1e-8 (relativ) überein, ausser bei 12 Genfer
    Gemeinden (66xx), wo ArcGIS abweicht bzw. Werte fehlen. Deshalb nur optional.
    """
    bikes = gpd.read_file(bikes_path, columns=[]).to_crs(paths.CRS)
    pieces = gpd.overlay(
        bikes, municipalities[["BFSNR", "geometry"]], how="intersection", keep_geom_type=True
    )
    pieces["length"] = pieces.geometry.length
    return pieces.groupby("BFSNR")["length"].agg(SUM_FREQ="size", SUM_LENGTH="sum").reset_index()


def load_street_lengths(path: Path = paths.INTERIM_STREET_LENGTHS) -> pd.DataFrame:
    """Länge des Strassennetzes pro Gemeinde aus dem QGIS-Schritt."""
    return pd.read_csv(path)[["BFSNR", "LENGTH"]]


def load_population(path: Path = paths.INTERIM_POPULATION) -> pd.DataFrame:
    """Ständige Wohnbevölkerung 2021 pro Gemeinde."""
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
    return municipalities["BFSNR"].map(counts).fillna(0).astype(float).rename("ACCIDENTS")


def classify(yes: pd.Series, bike: pd.Series, bike_threshold: float) -> pd.Series:
    """Bivariate Klassierung (Werte als Dezimalzahlen).

         2  viel Velowege, viele Ja      1  viel Velowege, wenige Ja
         0  wenig Velowege, viele Ja    -1  wenig Velowege, wenige Ja

    Ja-Schwelle = gerundeter Mittelwert aller Gemeinden (inkl. fehlender Werte als 0).
    """
    yes_threshold = round(float(yes.mean()), paths.YES_THRESHOLD_DECIMALS)
    good_bike = bike >= bike_threshold
    many_yes = yes >= yes_threshold
    value = np.select(
        [good_bike & many_yes, good_bike & ~many_yes, ~good_bike & many_yes],
        [2.0, 1.0, 0.0],
        default=-1.0,
    )
    return pd.Series(value, index=yes.index, name="VALUE")


def build_final(
    interim_dir: Path = paths.INTERIM_DIR, recompute_bike_lengths: bool = False
) -> gpd.GeoDataFrame:
    """Berechnet final_values im Speicher."""
    interim_dir = Path(interim_dir)
    gdf = load_municipalities(interim_dir / paths.INTERIM_RESULTS.name)
    gdf["ACCIDENTS"] = count_accidents(gdf, interim_dir / paths.INTERIM_ACCIDENTS.name)

    if recompute_bike_lengths:
        bike_lengths = compute_bike_lengths(gdf, interim_dir / paths.INTERIM_BIKES.name)
    else:
        bike_lengths = load_bike_lengths(interim_dir / paths.INTERIM_BIKE_LENGTHS.name)

    gdf = gdf.merge(bike_lengths, on="BFSNR", how="left")
    gdf = gdf.merge(
        load_population(interim_dir / paths.INTERIM_POPULATION.name), on="BFSNR", how="left"
    )
    # inner join: Gemeinden ohne Strassennetz-Wert fallen weg. Das betrifft nur BFS 389
    # (Meienried, gemeinsame Urne mit Büren a.A., ohne eigenes Resultat) – wie bisher.
    gdf = gdf.merge(
        load_street_lengths(interim_dir / paths.INTERIM_STREET_LENGTHS.name),
        on="BFSNR",
        how="inner",
    )

    # Veloweg-Anteil am Strassennetz in %, auf 3 Stellen gerundet wie im QGIS-Feldrechner
    bike_share = gdf["SUM_LENGTH"] / gdf["LENGTH"] * 100
    gdf["BIKE_STREET_PER"] = bike_share.round(paths.BIKE_STREET_PER_DECIMALS)

    # Fehlende Werte zählen als 0 (auch für die Schwellenwerte!), '...' = kein Resultat
    # (Gemeinden mit gemeinsamer Urne).
    gdf["YES_IN_PER"] = gdf["YES_IN_PER"].replace("...", "0").fillna(0).astype(float)
    fill_cols = ["BIKE_STREET_PER", "ACCIDENTS", "POP_TOTAL"]
    gdf[fill_cols] = gdf[fill_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    # Prozent -> Dezimal
    gdf["YES_IN_PER"] = gdf["YES_IN_PER"] / 100
    gdf["BIKE_STREET_PER"] = gdf["BIKE_STREET_PER"] / 100

    # Unfälle pro 100'000 EW; ohne Bevölkerungszahl -> 0 (x/0 = inf), 0/0 bleibt NaN
    per_100k = gdf["ACCIDENTS"] / gdf["POP_TOTAL"] * 100_000
    gdf["ACCIDENTS_PER_100K"] = per_100k.replace([np.inf, -np.inf], 0)

    gdf["VALUE"] = classify(gdf["YES_IN_PER"], gdf["BIKE_STREET_PER"], paths.BIKE_THRESHOLD)

    return gdf[paths.FINAL_COLUMNS]


def canton_accidents(final: pd.DataFrame) -> pd.DataFrame:
    """Ungewichteter Mittelwert der kommunalen Unfallraten pro Kanton (NaN ignoriert)."""
    df = final.groupby("KTNR")["ACCIDENTS_PER_100K"].mean().round(2).reset_index()
    return df


def main(
    output_dir: Path = paths.PROCESSED_DIR,
    interim_dir: Path = paths.INTERIM_DIR,
    recompute_bike_lengths: bool = False,
) -> gpd.GeoDataFrame:
    """Berechnet und schreibt final_values.geojson und canton_accidents.csv."""
    start = time.perf_counter()
    final = build_final(interim_dir, recompute_bike_lengths=recompute_bike_lengths)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / paths.FINAL_VALUES_NAME
    canton_path = output_dir / paths.CANTON_ACCIDENTS_NAME
    final.to_file(final_path, driver="GeoJSON")
    canton_accidents(final).to_csv(canton_path, index=False)

    print(f"Geschrieben: {final_path} ({len(final)} Gemeinden)")
    print(f"Geschrieben: {canton_path}")
    print(f"Build-Dauer: {time.perf_counter() - start:.1f} s")
    return final
