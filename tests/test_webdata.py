"""Tests für den Webkarten-Export."""

from pipeline.webdata import jenks_breaks


def test_jenks_separates_obvious_groups():
    values = [1, 2, 3, 10, 11, 12, 20, 21, 22, 40, 41]
    assert jenks_breaks(values, 4) == [3, 12, 22]
