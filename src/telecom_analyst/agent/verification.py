"""Confere se cada número da resposta veio de uma ferramenta ou da própria pergunta."""

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER = re.compile(
    r"(?<![\w.,/-])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[,.]\d+)?)"
    r"(?![\w/]|-\d)(?:\s*(mil|milhões|milhão|bilhões|bilhão)\b)?",
    re.IGNORECASE,
)
SCALES = {
    "mil": Decimal(1_000),
    "milhão": Decimal(1_000_000),
    "milhões": Decimal(1_000_000),
    "bilhão": Decimal(1_000_000_000),
    "bilhões": Decimal(1_000_000_000),
}
LIST_ITEM = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
SMALL_NUMBER_LIMIT = 12
FIRST_YEAR = 1990
LAST_YEAR = 2035


def _parse(raw: str) -> tuple[Decimal, int] | None:
    """Converte um número brasileiro e devolve o valor e suas casas decimais."""
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", raw):
        text = raw.replace(".", "").replace(",", ".")
    else:
        text = raw.replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    decimals = len(text.split(".")[1]) if "." in text else 0
    return value, decimals


def extract_numbers(text: str) -> list[tuple[str, Decimal, Decimal]]:
    """Devolve o texto, o valor e a tolerância de arredondamento de cada número."""
    found = []
    for match in NUMBER.finditer(LIST_ITEM.sub(" ", text)):
        parsed = _parse(match.group(1))
        if parsed is None:
            continue
        value, decimals = parsed
        scale = SCALES.get((match.group(2) or "").lower(), Decimal(1))
        tolerance = Decimal(10) ** -decimals / 2 * scale
        found.append((match.group(0).strip(), value * scale, tolerance))
    return found


def _is_trivial(value: Decimal) -> bool:
    """Números pequenos e anos aparecem em qualquer texto e não são dados citados."""
    is_year = value == value.to_integral() and FIRST_YEAR <= value <= LAST_YEAR
    return is_year or abs(value) <= SMALL_NUMBER_LIMIT


def flatten_numbers(rows: Iterable[Iterable[Any]]) -> list[Decimal]:
    values = []
    for row in rows:
        for cell in row:
            if isinstance(cell, bool):
                continue
            if isinstance(cell, int | float):
                values.append(Decimal(str(cell)))
            elif isinstance(cell, str) and re.fullmatch(r"-?\d+(\.\d+)?", cell):
                values.append(Decimal(cell))
    return values


def find_unsupported(answer: str, sources: list[Decimal], question: str) -> list[str]:
    """Lista os números da resposta sem origem nos resultados ou na pergunta."""
    allowed = sources + [value for _, value, _ in extract_numbers(question)]
    unsupported = []
    for text, value, tolerance in extract_numbers(answer):
        if _is_trivial(value):
            continue
        if not any(abs(abs(value) - abs(source)) <= tolerance for source in allowed):
            unsupported.append(text)
    return unsupported
