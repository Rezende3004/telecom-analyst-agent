from decimal import Decimal

import pytest

from telecom_analyst.agent.verification import extract_numbers, find_unsupported, flatten_numbers


def sources(*values: str) -> list[Decimal]:
    return [Decimal(value) for value in values]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("São 72.978 acessos", "72978"),
        ("São 1.234.567 acessos", "1234567"),
        ("O share é 56,8%", "56.8"),
        ("O HHI é 3520", "3520"),
        ("São 1,2 milhão de acessos", "1200000"),
        ("São 58 milhões", "58000000"),
        ("Cerca de 73 mil", "73000"),
    ],
)
def test_reads_brazilian_formats(text: str, expected: str) -> None:
    assert [value for _, value, _ in extract_numbers(text)] == [Decimal(expected)]


def test_accepts_value_from_results() -> None:
    assert find_unsupported("São 72.978 acessos.", sources("72978"), "") == []


def test_flags_invented_value() -> None:
    assert find_unsupported("São 99.999 acessos.", sources("72978"), "") == ["99.999"]


def test_accepts_rounded_value() -> None:
    assert find_unsupported("O share é 56,8%.", sources("56.7961"), "") == []


def test_accepts_scaled_rounding() -> None:
    assert find_unsupported("São 58 milhões.", sources("58075574"), "") == []


def test_rejects_wrong_scale() -> None:
    assert find_unsupported("São 58 mil.", sources("58075574"), "") == ["58 mil"]


def test_accepts_number_from_the_question() -> None:
    question = "Quais cidades têm mais de 50 mil habitantes?"

    assert find_unsupported("Cidades com mais de 50 mil habitantes.", [], question) == []


def test_ignores_years_and_small_numbers() -> None:
    assert find_unsupported("Em 2026, as 3 maiores cidades.", [], "") == []


def test_ignores_list_numbering_and_dates() -> None:
    text = "1. Goiânia\n2. Anápolis\nReferência 2026-09-01 e 09/2026."

    assert find_unsupported(text, [], "") == []


def test_flatten_ignores_text_and_booleans() -> None:
    assert flatten_numbers([["Goiânia", 10, True, 2.5, None, "12.5"]]) == sources(
        "10", "2.5", "12.5"
    )
