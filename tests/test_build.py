"""Tests der Pipeline: build reproduziert die versionierten Endresultate exakt
und die inhaltlichen Korrekturen bleiben erhalten."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from pipeline import build, paths


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("processed")
    build.main(output_dir=out)
    return out


@pytest.fixture(scope="module")
def reference():
    return gpd.read_file(paths.FINAL_VALUES)


def test_final_values_match_reference(built, reference):
    result = gpd.read_file(built / paths.FINAL_VALUES_NAME)

    assert list(result.columns) == paths.FINAL_COLUMNS
    assert list(result.columns) == list(reference.columns)
    assert len(result) == len(reference) == 2136
    assert result.crs == reference.crs
    assert (result["BFSNR"].to_numpy() == reference["BFSNR"].to_numpy()).all()

    # Klassierung muss exakt stimmen
    assert np.array_equal(result["VALUE"].to_numpy(), reference["VALUE"].to_numpy(), equal_nan=True)

    for col in reference.columns.drop("geometry"):
        a, b = result[col], reference[col]
        if pd.api.types.is_float_dtype(b):
            assert np.isclose(a, b, equal_nan=True).all(), col
        else:
            assert (a.to_numpy() == b.to_numpy()).all(), col

    assert result.geometry.geom_equals(reference.geometry).all()


def test_canton_accidents_match_reference(built):
    result = pd.read_csv(built / paths.CANTON_ACCIDENTS_NAME)
    reference = pd.read_csv(paths.CANTON_ACCIDENTS)
    pd.testing.assert_frame_equal(result, reference)


def test_bike_threshold():
    # Mittelwert der sechs Prix-Velo-Städte
    assert paths.BIKE_THRESHOLD == pytest.approx(0.064645, abs=1e-6)


def test_no_vote_is_no_data(built):
    """Gemeinden mit gemeinsamer Urne ('...') haben keinen Ja-Anteil und keine Klasse."""
    result = gpd.read_file(built / paths.FINAL_VALUES_NAME, ignore_geometry=True)
    no_vote = result["YES_IN_PER"].isna()
    assert sorted(result.loc[no_vote, "BFSNR"]) == [389, 408, 422, 535, 877]
    assert result.loc[no_vote, "VALUE"].isna().all()
    assert result.loc[~no_vote, "VALUE"].notna().all()


def test_every_municipality_has_population(built):
    result = gpd.read_file(built / paths.FINAL_VALUES_NAME, ignore_geometry=True)
    assert (result["POP_TOTAL"] > 0).all()
    assert result["ACCIDENTS_PER_100K"].notna().all()


def test_geneva_bike_lengths_complete(built):
    """Der frühere ArcGIS-Schritt hatte 9 Genfer Gemeinden ausgelassen."""
    result = gpd.read_file(built / paths.FINAL_VALUES_NAME, ignore_geometry=True)
    geneva = result[result["KTNR"] == 25]
    assert (geneva["BIKE_LENGTH"] > 0).sum() >= 44
    satigny = result.set_index("BFSNR").loc[6638, "BIKE_LENGTH"]
    assert satigny == pytest.approx(15278, rel=1e-3)


def test_accident_period():
    accidents = gpd.read_file(paths.INTERIM_ACCIDENTS, ignore_geometry=True)
    period = accidents["AccidentYear"] * 100 + accidents["AccidentMonth"]
    assert period.min() >= 201101
    assert period.max() == 201809
    # Oktober–Dezember der Vorjahre sind enthalten
    assert ((accidents["AccidentYear"] == 2017) & (accidents["AccidentMonth"] == 12)).any()
    assert len(accidents) == 30108


def test_canton_rate_is_weighted(built):
    canton = pd.read_csv(built / paths.CANTON_ACCIDENTS_NAME)
    expected = canton["ACCIDENTS"] / canton["POP_TOTAL"] * 100_000
    assert np.allclose(canton["ACCIDENTS_PER_100K"], expected, atol=0.01)
