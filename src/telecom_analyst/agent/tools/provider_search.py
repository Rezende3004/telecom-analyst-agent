"""Ferramenta find_provider: acha um provedor pelo nome, tolerando grafia e marca."""

from collections.abc import Callable
from functools import cached_property

from pydantic import BaseModel, Field

from telecom_analyst.agent.tools.base import Tool
from telecom_analyst.agent.tools.sql import Connect, execute
from telecom_analyst.algorithms.string_similarity import (
    jaro_winkler,
    normalize_company_name,
    trigram_similarity,
)

MAX_CANDIDATES = 5
MIN_SCORE = 0.55
MIN_JARO_WINKLER = 0.94
MAX_TYPO_LENGTH_DIFFERENCE = 2
CONTAINED_SCORE = 0.75
AMBIGUITY_MARGIN = 0.05
# Palavras comuns em nomes de provedores que aproximam empresas sem relação entre si.
GENERIC_WORDS = frozenset({"BANDA", "FIBRA", "INTERNET", "LARGA", "PROVEDOR", "REDE"})
NAMES_QUERY = "SELECT nome, agente_nome, acessos_atuais FROM semantic.nomes_provedores"


class FindProviderInput(BaseModel):
    nome: str = Field(description="Nome do provedor, como aparece na pergunta.")


class ProviderCandidate(BaseModel):
    agente_nome: str
    nome_encontrado: str
    acessos_atuais: int
    similaridade: float


class FindProviderResult(BaseModel):
    candidatos: list[ProviderCandidate]
    orientacao: str


def distinctive_name(name: str) -> str:
    """Normaliza o nome e tira palavras genéricas, salvo se não sobrar mais nada."""
    normalized = normalize_company_name(name)
    words = [word for word in normalized.split() if word not in GENERIC_WORDS]
    return " ".join(words) or normalized


def similarity(query: str, name: str) -> float:
    """Pontua dois nomes normalizados: igual, contido, parecido ou com erro de grafia."""
    if not query or not name:
        return 0.0
    if query == name:
        return 1.0
    score = trigram_similarity(query, name)
    if set(query.split()) <= set(name.split()):
        score = max(score, CONTAINED_SCORE)
    # Sem o limite de tamanho, o bônus de prefixo aproxima nomes como HIPER e HIPERVIA.
    if abs(len(query) - len(name)) <= MAX_TYPO_LENGTH_DIFFERENCE:
        typo = jaro_winkler(query, name)
        if typo >= MIN_JARO_WINKLER:
            score = max(score, typo)
    return score


def _guidance(candidates: list[ProviderCandidate]) -> str:
    if not candidates:
        return "Nenhum provedor encontrado. Diga que não achou esse nome e não informe números."
    close = [
        c for c in candidates if candidates[0].similaridade - c.similaridade <= AMBIGUITY_MARGIN
    ]
    if len(close) > 1 and candidates[0].similaridade < 1:
        return "Nomes parecidos. Use o primeiro e diga na resposta qual provedor foi considerado."
    return "Use `agente_nome` do primeiro candidato nos filtros da SQL."


class ProviderIndex:
    """Índice em memória dos nomes, carregado na primeira busca."""

    def __init__(self, load: Callable[[], list[list[object]]]) -> None:
        self._load = load

    @cached_property
    def _entries(self) -> list[tuple[str, str, str, int]]:
        entries = []
        for name, agent, accesses in self._load():
            normalized = distinctive_name(str(name))
            if normalized:
                entries.append((normalized, str(name), str(agent), int(float(str(accesses)))))
        return entries

    def search(self, query: str) -> FindProviderResult:
        normalized = distinctive_name(query)
        best: dict[str, ProviderCandidate] = {}
        for entry, name, agent, accesses in self._entries:
            score = similarity(normalized, entry)
            if score < MIN_SCORE:
                continue
            candidate = ProviderCandidate(
                agente_nome=agent,
                nome_encontrado=name,
                acessos_atuais=accesses,
                similaridade=round(score, 2),
            )
            # Agentes diferentes podem ter o mesmo nome: vale o de nota maior e, no empate, o ativo.
            known = best.get(agent)
            if known is None or (candidate.similaridade, accesses) > (
                known.similaridade,
                known.acessos_atuais,
            ):
                best[agent] = candidate
        ranked = sorted(best.values(), key=lambda c: (-c.similaridade, -c.acessos_atuais))
        candidates = ranked[:MAX_CANDIDATES]
        return FindProviderResult(candidatos=candidates, orientacao=_guidance(candidates))


def make_find_provider_tool(connect: Connect) -> Tool:
    index = ProviderIndex(lambda: execute(connect, NAMES_QUERY).rows)

    def handler(arguments: FindProviderInput) -> FindProviderResult:
        return index.search(arguments.nome)

    return Tool(
        name="find_provider",
        description=(
            "Encontra o provedor ou grupo pelo nome, tolerando erro de grafia, marca comercial "
            "e razão social. Chame antes de consultar dados de um provedor citado por nome e "
            "use o `agente_nome` devolvido na SQL."
        ),
        input_model=FindProviderInput,
        handler=handler,
    )
