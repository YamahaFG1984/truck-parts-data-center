import pytest

from apps.core.utils import normalize_part_no, split_numbers


@pytest.mark.parametrize("raw, expected", [
    ("81.50804-6004", "81508046004"),
    ("A 000 420 20 20", "A0004202020"),
    ("20 837 792", "20837792"),
    ("w962", "W962"),
    ("OE: 20837792", "20837792"),
    ("０８１２３４５", "0812345"),  # full-width digits, leading zero kept
    ("  HU 12 140 x ", "HU12140X"),
    ("", ""),
    (None, ""),
])
def test_normalize_part_no(raw, expected):
    assert normalize_part_no(raw) == expected


def test_split_numbers_keeps_spaced_numbers_together():
    assert split_numbers("20837792 / 21122012; 81.50804-6004") == ["20837792", "21122012", "81.50804-6004"]
    assert split_numbers("Febi   863  37") == ["Febi   863  37"]
    assert split_numbers(["A 000 420 20 20"]) == ["A 000 420 20 20"]
