"""Regressionstest: build reproduziert die versionierten Endresultate exakt."""

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
    assert len(result) == len(reference) == 2135
    assert result.crs == reference.crs
    assert (result["BFSNR"].to_numpy() == reference["BFSNR"].to_numpy()).all()

    # Klassierung muss exakt stimmen
    assert (result["VALUE"].to_numpy() == reference["VALUE"].to_numpy()).all()

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
