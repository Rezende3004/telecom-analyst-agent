import random

import pytest

from telecom_analyst.algorithms.string_similarity import (
    jaro,
    jaro_winkler,
    normalize_company_name,
    trigram_similarity,
)
from telecom_analyst.algorithms.union_find import UnionFind


def test_union_joins_transitively() -> None:
    sets: UnionFind[str] = UnionFind()
    sets.union("a", "b")
    sets.union("b", "c")

    assert sets.connected("a", "c")


def test_separate_sets_stay_apart() -> None:
    sets: UnionFind[str] = UnionFind()
    sets.union("a", "b")
    sets.union("c", "d")

    assert not sets.connected("a", "d")


def test_union_reports_whether_it_merged() -> None:
    sets: UnionFind[str] = UnionFind()

    assert sets.union("a", "b") is True
    assert sets.union("b", "a") is False


def test_groups_include_singletons() -> None:
    sets = UnionFind(["solo"])
    sets.union("a", "b")

    assert sorted(sets.groups(), key=len) == [{"solo"}, {"a", "b"}]


def test_long_chain_does_not_hit_recursion_limit() -> None:
    size = 200_000
    sets: UnionFind[int] = UnionFind()
    for item in range(size):
        sets.union(item, item + 1)

    assert sets.connected(0, size)
    assert len(sets.groups()) == 1


def test_matches_naive_implementation_on_random_edges() -> None:
    rng = random.Random(42)  # noqa: S311
    nodes = range(300)
    sets = UnionFind(nodes)
    labels = {node: node for node in nodes}

    for _ in range(400):
        first, second = rng.choice(nodes), rng.choice(nodes)
        sets.union(first, second)
        old, new = labels[first], labels[second]
        labels = {node: new if label == old else label for node, label in labels.items()}

    for _ in range(2000):
        first, second = rng.choice(nodes), rng.choice(nodes)
        assert sets.connected(first, second) == (labels[first] == labels[second])


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("MARTHA", "MARHTA", 0.944444),
        ("DIXON", "DICKSONX", 0.766667),
        ("CRATE", "TRACE", 0.733333),
        ("ABC", "XYZ", 0.0),
        ("", "ABC", 0.0),
        ("ABC", "ABC", 1.0),
        ("", "", 1.0),
    ],
)
def test_jaro_reference_values(first: str, second: str, expected: float) -> None:
    assert jaro(first, second) == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [("MARTHA", "MARHTA", 0.961111), ("DIXON", "DICKSONX", 0.813333), ("ABC", "XYZ", 0.0)],
)
def test_jaro_winkler_reference_values(first: str, second: str, expected: float) -> None:
    assert jaro_winkler(first, second) == pytest.approx(expected, abs=1e-5)


def test_odd_transposition_count_rounds_down() -> None:
    # 6 caracteres em comum e 5 fora de ordem: 5 // 2 = 2, como no strcmp95 de Winkler.
    assert jaro("ABCDEF", "CABDFE") == pytest.approx(0.888889, abs=1e-5)


def test_prefix_bonus_only_applies_above_threshold() -> None:
    first, second = "ABXXXX", "ABYYYY"

    assert jaro(first, second) <= 0.7
    assert jaro_winkler(first, second) == jaro(first, second)


def test_jaro_is_symmetric_on_random_strings() -> None:
    rng = random.Random(7)  # noqa: S311
    for _ in range(500):
        first = "".join(rng.choices("ABCD", k=rng.randint(1, 12)))
        second = "".join(rng.choices("ABCD", k=rng.randint(1, 12)))
        assert jaro(first, second) == pytest.approx(jaro(second, first))
        assert 0.0 <= jaro_winkler(first, second) <= 1.0


def test_trigrams_tolerate_reordered_words() -> None:
    reordered = trigram_similarity("REDE NORTE FIBRA", "FIBRA REDE NORTE")

    assert reordered > trigram_similarity("REDE NORTE FIBRA", "VALE SUL NET")
    assert reordered > 0.6


def test_trigram_similarity_edges() -> None:
    assert trigram_similarity("ABC", "ABC") == 1.0
    assert trigram_similarity("", "ABC") == 0.0


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Vale Fibra Telecomunicações Ltda - ME", "VALE FIBRA"),
        ("REDE NORTE S/A", "REDE NORTE"),
        ("Rede Norte S.A.", "REDE NORTE"),
        ("Conexão & Cia. Serviços", "CONEXAO CIA"),
    ],
)
def test_normalize_company_name(name: str, expected: str) -> None:
    assert normalize_company_name(name) == expected


def test_me_inside_a_word_is_kept() -> None:
    assert normalize_company_name("MEGA NET") == "MEGA NET"
