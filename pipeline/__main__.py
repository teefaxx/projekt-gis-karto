"""Kommandozeile: ``python -m pipeline <befehl>`` (vom Repo-Root oder überall).

Befehle:
    prepare   Rohdaten -> data/interim/ (benötigt data/raw/, nicht im Repo)
    build     data/interim/ -> data/processed/
    analyze   Korrelationen ausgeben, Diagramme nach reports/figures/
    webdata   Daten für die Web-Karte (falls pipeline/webdata.py vorhanden)
    all       prepare (falls Rohdaten vorhanden) + build + analyze (+ webdata)
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from . import paths


def _webdata_main():
    """Lädt pipeline.webdata.main erst bei Bedarf; None, falls nicht vorhanden."""
    try:
        module = importlib.import_module(f"{__package__}.webdata")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__package__}.webdata":
            return None
        raise
    return getattr(module, "main", None)


def _raw_available() -> bool:
    return paths.RAW_DIR.is_dir() and any(paths.RAW_DIR.iterdir())


def run_prepare(args: argparse.Namespace) -> None:
    from . import prepare

    prepare.main()


def run_build(args: argparse.Namespace) -> None:
    from . import build

    build.main(output_dir=args.output_dir)


def run_analyze(args: argparse.Namespace) -> None:
    from . import analysis

    analysis.main(
        final_path=args.output_dir / paths.FINAL_VALUES_NAME, figures_dir=args.figures_dir
    )


def run_webdata(args: argparse.Namespace) -> None:
    main = _webdata_main()
    if main is None:
        sys.exit("pipeline/webdata.py mit einer Funktion main() ist nicht vorhanden.")
    main()


def run_all(args: argparse.Namespace) -> None:
    if _raw_available():
        run_prepare(args)
    else:
        print(f"Hinweis: {paths.RAW_DIR} fehlt -> prepare übersprungen, nutze data/interim/.")
    run_build(args)
    run_analyze(args)
    if _webdata_main() is not None:
        run_webdata(args)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description="Datenpipeline Velowege-Abstimmung 2018.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        return p

    add("prepare", run_prepare, "Rohdaten (data/raw/) -> data/interim/")
    p_build = add("build", run_build, "data/interim/ -> data/processed/")
    p_analyze = add("analyze", run_analyze, "Korrelationen und Diagramme")
    add("webdata", run_webdata, "Daten für die Web-Karte (pipeline/webdata.py)")
    p_all = add("all", run_all, "prepare (falls möglich), build, analyze, webdata")

    for p in (p_build, p_analyze, p_all):
        p.add_argument(
            "--output-dir",
            type=Path,
            default=paths.PROCESSED_DIR,
            help="Verzeichnis für final_values.geojson / canton_accidents.csv "
            "(Standard: data/processed/)",
        )
    for p in (p_analyze, p_all):
        p.add_argument(
            "--figures-dir",
            type=Path,
            default=paths.FIGURES_DIR,
            help="Zielordner der Diagramme (Standard: reports/figures/)",
        )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    from .prepare import RawDataMissingError

    args = parse_args(argv)
    try:
        args.func(args)
    except RawDataMissingError as exc:
        sys.exit(f"Fehler: {exc}")


if __name__ == "__main__":
    main()
