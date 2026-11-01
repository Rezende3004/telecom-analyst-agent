import pytest

from telecom_analyst.agent.entities import HomonymIndex
from telecom_analyst.agent.tools.provider_search import ProviderIndex, similarity
from telecom_analyst.algorithms.string_similarity import normalize_company_name

NAMES: list[list[object]] = [
    ["Vale Fibra", "Vale Fibra", 1800],
    ["VALE TELECOM LTDA", "Vale Fibra", 1800],
    ["NORTE NET", "GRUPO NORTE", 500000],
    ["REDE NORTE TELECOMUNICACOES S.A.", "GRUPO NORTE", 500000],
    ["Sul Conecta", "Sul Conecta", 30],
    ["Sul Conecta Mais", "Sul Conecta Mais", 20000],
]


def index() -> ProviderIndex:
    return ProviderIndex(lambda: NAMES)


def test_finds_commercial_name() -> None:
    result = index().search("Vale Fibra")

    assert result.candidatos[0].agente_nome == "Vale Fibra"
    assert result.candidatos[0].similaridade == 1.0


def test_finds_brand_inside_a_group() -> None:
    assert index().search("Norte Net").candidatos[0].agente_nome == "GRUPO NORTE"


def test_ignores_corporate_suffixes() -> None:
    result = index().search("Vale Telecomunicações Ltda - ME")

    assert result.candidatos[0].agente_nome == "Vale Fibra"


def test_tolerates_typo() -> None:
    assert index().search("Valle Fibra").candidatos[0].agente_nome == "Vale Fibra"


def test_tolerates_missing_accent_and_case() -> None:
    assert index().search("sul cônecta").candidatos[0].agente_nome == "Sul Conecta"


def test_unknown_name_returns_no_candidates() -> None:
    result = index().search("Operadora Inexistente")

    assert result.candidatos == []
    assert "não informe números" in result.orientacao


def test_same_agent_appears_once() -> None:
    names = [candidate.agente_nome for candidate in index().search("Norte").candidatos]

    assert names.count("GRUPO NORTE") == 1


def test_loads_names_only_once() -> None:
    calls = []

    def load() -> list[list[object]]:
        calls.append(1)
        return NAMES

    search_index = ProviderIndex(load)
    search_index.search("Norte")
    search_index.search("Vale")

    assert len(calls) == 1


def test_same_name_keeps_the_agent_with_most_accesses() -> None:
    names: list[list[object]] = [
        ["BETA", "BETA", 0],
        ["BETA", "BETA", 900000],
        ["Beta", "Beta", 2000],
    ]

    result = ProviderIndex(lambda: names).search("Beta")

    assert result.candidatos[0].agente_nome == "BETA"
    assert result.candidatos[0].acessos_atuais == 900000


def test_longer_name_with_same_prefix_is_not_a_typo() -> None:
    result = ProviderIndex(lambda: [["Hiper", "Hiper", 10]]).search("Hipermegavia")

    assert result.candidatos == []


def test_shared_generic_word_is_not_a_match() -> None:
    result = ProviderIndex(lambda: [["Alfanet Internet", "Alfanet", 10]]).search("Zeta Internet")

    assert result.candidatos == []


def test_name_with_only_generic_words_stays_searchable() -> None:
    result = ProviderIndex(lambda: [["Rede Fibra", "Rede Fibra", 10]]).search("Rede Fibra")

    assert result.candidatos[0].agente_nome == "Rede Fibra"


def test_accepts_accesses_as_decimal_from_the_database() -> None:
    result = ProviderIndex(lambda: [["Vale Fibra", "Vale Fibra", 1799.0]]).search("Vale Fibra")

    assert result.candidatos[0].acessos_atuais == 1799


def test_exact_match_beats_longer_name() -> None:
    assert index().search("Sul Conecta").candidatos[0].agente_nome == "Sul Conecta"


@pytest.mark.parametrize(("query", "name"), [("", "NORTE"), ("NORTE", "")])
def test_empty_names_have_no_similarity(query: str, name: str) -> None:
    assert similarity(query, name) == 0.0


def test_generic_words_alone_do_not_match() -> None:
    assert normalize_company_name("Telecomunicações Ltda") == ""
    assert index().search("Telecomunicações Ltda").candidatos == []


MUNICIPALITIES = [
    ("Palmas", "TO", "Tocantins"),
    ("Palmas", "PR", "Paraná"),
    ("Bom Jesus", "PI", "Piauí"),
    ("Bom Jesus", "RS", "Rio Grande do Sul"),
    ("Goiânia", "GO", "Goiás"),
]


def homonyms() -> HomonymIndex:
    return HomonymIndex(MUNICIPALITIES)


def test_warns_about_homonym() -> None:
    note = homonyms().note("Quantos acessos existem em Palmas?")

    assert note is not None
    assert "PR, TO" in note


def test_unique_city_needs_no_warning() -> None:
    assert homonyms().note("Quantos acessos existem em Goiânia?") is None


@pytest.mark.parametrize(
    "question",
    ["Quantos acessos há em Palmas (TO)?", "Quantos acessos há em Palmas, no Tocantins?"],
)
def test_no_warning_when_state_is_given(question: str) -> None:
    assert homonyms().note(question) is None


def test_ignores_name_inside_another_word() -> None:
    assert homonyms().note("Quantas palmasinhas existem?") is None


def test_handles_accents_in_the_question() -> None:
    assert homonyms().note("E em BOM JESÚS?") is not None
