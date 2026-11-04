"""Alle Pfade und Konstanten der Pipeline.

Pfade sind relativ zum Paket aufgelöst, die Skripte funktionieren daher
unabhängig vom aktuellen Arbeitsverzeichnis.
"""

from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# Verzeichnisse
# --------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # nicht im Repo (.gitignore), Download-Link abgelaufen
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = ROOT_DIR / "reports" / "figures"

# --------------------------------------------------------------------------
# Rohdaten (Layout wie im ehemaligen data.zip, jetzt unter data/raw/)
# --------------------------------------------------------------------------
RAW_BFS_SHP = RAW_DIR / "shp_bfs" / "g1g23.shp"  # BFS Generalisierte Gemeindegrenzen 2023
RAW_RESULTS_XLSX = RAW_DIR / "results" / "Resultate.xlsx"  # BFS Abstimmungsresultate
RAW_ACCIDENTS_JSON = RAW_DIR / "accidents" / "accidents.json"  # ASTRA Strassenverkehrsunfälle
RAW_OSM_ROADS_SHP = (
    RAW_DIR / "OSM_new" / "switzerland-latest-free.shp" / "gis_osm_roads_free_1.shp"
)  # Geofabrik OSM-Export
RAW_VELOLAND_SHP = RAW_DIR / "velo" / "Weg.shp"  # SchweizMobil Veloland
RAW_POPULATION_CSV = RAW_DIR / "bevoelkerung" / "pop_2021.csv"  # BFS STAT-TAB, Bestand 1.1.2021

# --------------------------------------------------------------------------
# Zwischenstände (im Repo versioniert)
# --------------------------------------------------------------------------
INTERIM_RESULTS = INTERIM_DIR / "results_bfs.geojson"
INTERIM_ACCIDENTS = INTERIM_DIR / "accidents.geojson"
INTERIM_BIKES = INTERIM_DIR / "bikes.geojson"
# Manueller ArcGIS-Schritt (Summe Veloweglänge pro Gemeinde), sep=";":
# Spalten BFS;FREQUENCY;SUM_Shape_Length
INTERIM_BIKE_LENGTHS = INTERIM_DIR / "bike_lengths_arcgis.csv"
# Manueller QGIS-Schritt (Länge Strassennetz pro Gemeinde): BFSNR,LENGTH,COUNT
INTERIM_STREET_LENGTHS = INTERIM_DIR / "street_lengths_qgis.csv"
INTERIM_POPULATION = INTERIM_DIR / "population_2021.csv"  # BFSNR,POP_TOTAL

# --------------------------------------------------------------------------
# Endresultate
# --------------------------------------------------------------------------
FINAL_VALUES_NAME = "final_values.geojson"
CANTON_ACCIDENTS_NAME = "canton_accidents.csv"
FINAL_VALUES = PROCESSED_DIR / FINAL_VALUES_NAME
CANTON_ACCIDENTS = PROCESSED_DIR / CANTON_ACCIDENTS_NAME

# --------------------------------------------------------------------------
# Konstanten
# --------------------------------------------------------------------------
CRS = "EPSG:2056"  # CH1903+ / LV95

# OSM-Klasse "cycleway" im Geofabrik-Shapefile (fclass code 5152)
OSM_CYCLEWAY_CODE = 5152

# Unfallfilter aus accidents_data.py: Monat <= 9 UND Jahr <= 2018.
# Achtung: Das schliesst Oktober-Dezember *aller* Jahre aus (vermutlich war
# "bis September 2018" gemeint). Unverändert übernommen, um die Resultate zu erhalten.
ACCIDENT_MAX_YEAR = 2018
ACCIDENT_MAX_MONTH = 9

# Veloweg-Anteil (Velowege / Strassennetz) der Prix-Velo-Städte, als Dezimalzahl.
# Quelle: https://www.prixvelo.ch/de/prix-velo-infrastruktur
PRIXVELO_BIKE_SHARES = {
    "Biel": 0.0499,
    "Chur": 0.0538,
    "Solothurn": 0.07373,
    "Basel": 0.07689,
    "Luzern": 0.06192,
    "Bern": 0.07163,
}
# Schwelle "gute Veloinfrastruktur" = Mittelwert der Prix-Velo-Städte (≈ 0.06465)
BIKE_THRESHOLD = float(np.mean(list(PRIXVELO_BIKE_SHARES.values())))
# Die Ja-Schwelle ist datenabhängig: round(mean(YES_IN_PER), 2) über alle Gemeinden
# (siehe build.classify). Nachkommastellen dafür:
YES_THRESHOLD_DECIMALS = 2

# Rundung des Veloweg-Anteils in % wie im ursprünglichen QGIS-Feldrechner
BIKE_STREET_PER_DECIMALS = 3

# Spalten (und Reihenfolge) von final_values.geojson
FINAL_COLUMNS = [
    "BFSNR",
    "YES_IN_PER",
    "BIKE_STREET_PER",
    "VALUE",
    "ACCIDENTS",
    "ACCIDENTS_PER_100K",
    "POP_TOTAL",
    "GMDNAME",
    "BZNR",
    "KTNR",
    "E_CNTR",
    "N_CNTR",
    "geometry",
]
