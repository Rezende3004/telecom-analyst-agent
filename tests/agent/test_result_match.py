import pytest
from evals.metrics.result_match import results_match, values_match


@pytest.mark.parametrize(
    ("expected", "actual", "matches"),
    [
        (72978, 72978.0, True),
        (17.19, 17.186, True),
        (100.0, 100.4, True),
        (100.0, 101.0, False),
        (0.0, 0.009, True),
        (0.0, 0.5, False),
        ("Goiânia", " goiânia ", True),
        ("Goiânia", "Goiás", False),
        (None, None, True),
        (None, 0, False),
        ("2026-09-01", "2026-09-01", True),
    ],
)
def test_values_match(expected: object, actual: object, matches: bool) -> None:
    assert values_match(expected, actual) is matches


def test_accepts_extra_columns() -> None:
    assert results_match([[72978]], [["Anápolis", 72978]])


def test_rejects_wrong_value() -> None:
    assert not results_match([[72978]], [[143633]])


def test_rejects_extra_rows() -> None:
    assert not results_match([["Goiânia"]], [["Goiânia"], ["Anápolis"]])


def test_rejects_missing_rows() -> None:
    assert not results_match([["Goiânia"], ["Anápolis"]], [["Goiânia"]])


def test_ignores_row_order_by_default() -> None:
    assert results_match([["a", 1], ["b", 2]], [["b", 2], ["a", 1]])


def test_enforces_order_when_ranking() -> None:
    assert not results_match([["a"], ["b"]], [["b"], ["a"]], ordered=True)
    assert results_match([["a"], ["b"]], [["a"], ["b"]], ordered=True)


def test_accepts_columns_in_another_order() -> None:
    assert results_match([["a", 1]], [[1, "a"]])


def test_keeps_values_paired_within_rows() -> None:
    expected = [["a", 1], ["b", 2]]

    assert not results_match(expected, [["a", 2], ["b", 1]])


def test_rejects_fewer_columns_than_reference() -> None:
    assert not results_match([["a", 1]], [["a"]])


def test_empty_results_match_only_each_other() -> None:
    assert results_match([], [])
    assert not results_match([[1]], [])


def test_duplicate_values_count_as_separate_rows() -> None:
    assert not results_match([["a"], ["a"]], [["a"], ["b"]])
