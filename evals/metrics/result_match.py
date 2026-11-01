"""Execution accuracy: compara resultados de consultas, nunca o texto da SQL.

O resultado do agente passa se contiver todas as colunas de referência com os mesmos valores
e o mesmo número de linhas. Colunas extras são aceitas, porque trazer o nome da cidade junto
do valor pedido não é erro. A ordem só conta quando a pergunta pede um ranking.
"""

from collections.abc import Iterator, Sequence
from itertools import permutations
from typing import Any

RELATIVE_TOLERANCE = 0.005
ABSOLUTE_TOLERANCE = 0.01
MAX_EXTRA_COLUMNS = 8

Rows = Sequence[Sequence[Any]]


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def values_match(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected is actual
    if _is_number(expected) and _is_number(actual):
        margin = max(ABSOLUTE_TOLERANCE, abs(expected) * RELATIVE_TOLERANCE)
        return bool(abs(expected - actual) <= margin)
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _column(rows: Rows, index: int) -> list[Any]:
    return [row[index] for row in rows]


def _same_bag(expected: list[Any], actual: list[Any]) -> bool:
    """Compara colunas sem ordem. Ordenar antes só funciona bem para valores exatos."""
    remaining = list(actual)
    for value in expected:
        for position, candidate in enumerate(remaining):
            if values_match(value, candidate):
                del remaining[position]
                break
        else:
            return False
    return not remaining


def _candidates(expected: Rows, actual: Rows, width: int) -> list[list[int]]:
    result = []
    for index in range(len(expected[0])):
        wanted = _column(expected, index)
        result.append([col for col in range(width) if _same_bag(wanted, _column(actual, col))])
    return result


def _mappings(candidates: list[list[int]], width: int) -> Iterator[tuple[int, ...]]:
    allowed = [set(options) for options in candidates]
    for mapping in permutations(range(width), len(candidates)):
        if all(column in allowed[index] for index, column in enumerate(mapping)):
            yield mapping


def _rows_match(expected: Rows, actual: Rows, mapping: tuple[int, ...], ordered: bool) -> bool:
    projected = [tuple(row[column] for column in mapping) for row in actual]
    if ordered:
        return all(
            all(values_match(a, b) for a, b in zip(left, right, strict=True))
            for left, right in zip(expected, projected, strict=True)
        )
    remaining = list(projected)
    for row in expected:
        for position, candidate in enumerate(remaining):
            if all(values_match(a, b) for a, b in zip(row, candidate, strict=True)):
                del remaining[position]
                break
        else:
            return False
    return True


def results_match(expected: Rows, actual: Rows, *, ordered: bool = False) -> bool:
    if len(expected) != len(actual):
        return False
    if not expected:
        return True
    width = len(actual[0])
    if width < len(expected[0]) or width > len(expected[0]) + MAX_EXTRA_COLUMNS:
        return False
    candidates = _candidates(expected, actual, width)
    if not all(candidates):
        return False
    return any(
        _rows_match(expected, actual, mapping, ordered) for mapping in _mappings(candidates, width)
    )
