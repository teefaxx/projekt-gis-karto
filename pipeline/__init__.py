"""Datenpipeline: Abstimmung «Bundesbeschluss Velowege» (23.09.2018) vs. Veloinfrastruktur.

Module:
    paths     Pfade und Konstanten (Schwellenwerte, CRS, Filter)
    prepare   Rohdaten (data/raw/) -> Zwischenstände (data/interim/)
    build     Zwischenstände -> Endresultat (data/processed/)
    analysis  Korrelationen und Streudiagramme (reports/figures/)

Aufruf vom Repo-Root: ``python -m pipeline --help``.
"""

__all__ = ["paths"]
