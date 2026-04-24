"""
Tests de funciones puras del dominio de indicadores. No requieren DB.
"""

from app.modules.indicators.services.strategy_progress_service import (
    _parse_indicator_ids,
    _sum_any_numeric,
    _record_matches_year,
)


class _FakeRecord:
    def __init__(self, data):
        self.data = data


# ─── _parse_indicator_ids ──────────────────────────────────────────────
def test_parse_single_id():
    assert _parse_indicator_ids("76") == [76]
    assert _parse_indicator_ids(76) == [76]
    assert _parse_indicator_ids(" 76 ") == [76]


def test_parse_csv():
    assert _parse_indicator_ids("163,162,164") == [163, 162, 164]
    assert _parse_indicator_ids("163, 162 , 164") == [163, 162, 164]


def test_parse_json_array():
    assert _parse_indicator_ids("[163,162,164]") == [163, 162, 164]


def test_parse_list_input():
    assert _parse_indicator_ids([163, 162, 164]) == [163, 162, 164]


def test_parse_dedups_preserve_order():
    assert _parse_indicator_ids("163,162,163,164,162") == [163, 162, 164]


def test_parse_empty_or_invalid():
    assert _parse_indicator_ids("") == []
    assert _parse_indicator_ids(None) == []
    assert _parse_indicator_ids("abc") == []


# ─── _sum_any_numeric ───────────────────────────────────────────────────
def test_sum_sum_group_dict():
    assert _sum_any_numeric({"ene": 100, "feb": 250, "mar": 521}) == 871


def test_sum_plain_number():
    assert _sum_any_numeric(42) == 42
    assert _sum_any_numeric(0) == 0


def test_sum_string_numeric():
    assert _sum_any_numeric("42.5") == 42.5


def test_sum_none_and_garbage():
    assert _sum_any_numeric(None) == 0
    assert _sum_any_numeric("abc") == 0
    assert _sum_any_numeric(True) == 0   # los booleanos NO se suman


def test_sum_nested():
    assert _sum_any_numeric({"data": {"x": {"y": 10}, "z": 5}}) == 15


# ─── _record_matches_year ───────────────────────────────────────────────
def test_record_matches_with_explicit_year_field():
    assert _record_matches_year(_FakeRecord({"año": 2025}), 2025) is True
    assert _record_matches_year(_FakeRecord({"año": "2025"}), 2025) is True
    assert _record_matches_year(_FakeRecord({"año": 2024}), 2025) is False
    assert _record_matches_year(_FakeRecord({"year": 2026}), 2026) is True


def test_record_matches_with_yyyy_mm_in_mes():
    assert _record_matches_year(_FakeRecord({"mes": "2025-01"}), 2025) is True
    assert _record_matches_year(_FakeRecord({"mes": "2025/03"}), 2025) is True
    assert _record_matches_year(_FakeRecord({"mes": "2024-12"}), 2025) is False


def test_record_matches_legacy_falls_back_true():
    # Sin campo de año detectable → no se filtra (comportamiento legacy).
    assert _record_matches_year(_FakeRecord({"mes": "Enero"}), 2025) is True
    assert _record_matches_year(_FakeRecord({}), 2025) is True
