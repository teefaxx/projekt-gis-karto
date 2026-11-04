"""Korrelationen und Streudiagramme auf Basis von final_values.geojson.

Port von src/corr.py und src/plots.py.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # ohne Fenster, nur Dateien

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from . import paths  # noqa: E402

PLOTS = [
    {
        "x": "YES_IN_PER",
        "y": "BIKE_STREET_PER",
        "title": "Zusammenhang zwischen Ja-Stimmen und Veloweg-Anteil",
        "x_label": "Ja-Stimmen in %",
        "y_label": "Veloweg-Anteil in %",
        "filename": "bike_path_corr",
    },
    {
        "x": "YES_IN_PER",
        "y": "ACCIDENTS_PER_100K",
        "title": "Zusammenhang zwischen Ja-Stimmen und Velounfällen",
        "x_label": "Ja-Stimmen in %",
        "y_label": "Velounfälle pro 100k Einwohner",
        "filename": "accidents_corr",
    },
]


def correlations(df: pd.DataFrame) -> dict[str, float]:
    """Pearson-Korrelation der Ja-Anteile mit Veloweg-Anteil bzw. Unfallrate.

    Paarweise ohne fehlende Werte (Gemeinden ohne eigenes Abstimmungsresultat).
    """
    return {
        "YES_IN_PER ~ BIKE_STREET_PER": df["YES_IN_PER"].corr(df["BIKE_STREET_PER"]),
        "YES_IN_PER ~ ACCIDENTS_PER_100K": df["YES_IN_PER"].corr(df["ACCIDENTS_PER_100K"]),
    }


def plot_corr(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    x_label: str,
    y_label: str,
    filename: str,
    figures_dir: Path,
    dot_color: str = "blue",
    reg_color: str = "red",
) -> Path:
    """Streudiagramm mit linearer Regressionsgeraden (inkl. 95%-Konfidenzband)."""
    fig, ax = plt.subplots(figsize=(10, 10))
    df.plot.scatter(x=x, y=y, c=dot_color, ax=ax)
    sns.regplot(data=df, x=x, y=y, scatter=False, color=reg_color, ax=ax)
    ax.set_title(title)
    ax.grid(True)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    out = figures_dir / f"{filename}.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def main(final_path: Path = paths.FINAL_VALUES, figures_dir: Path = paths.FIGURES_DIR) -> dict:
    """Gibt die Korrelationen aus und schreibt die Diagramme."""
    df = gpd.read_file(final_path, ignore_geometry=True)
    df = df.dropna(subset=["YES_IN_PER", "BIKE_STREET_PER"])
    # Anteile für die Diagramme in Prozent
    df[["YES_IN_PER", "BIKE_STREET_PER"]] = df[["YES_IN_PER", "BIKE_STREET_PER"]] * 100

    corr = correlations(df)
    print(f"Pearson-Korrelation (n = {len(df)} Gemeinden mit eigenem Resultat):")
    for name, r in corr.items():
        print(f"  {name}: r = {r:.4f}")

    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    for spec in PLOTS:
        print(f"Geschrieben: {plot_corr(df, figures_dir=figures_dir, **spec)}")
    return corr
