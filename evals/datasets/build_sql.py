"""Gera sql.jsonl a partir de modelos de pergunta. O resultado esperado nunca fica aqui.

A divisão entre `dev` e `test` é feita por modelo, para que a mesma pergunta com outra cidade
não vaze para o teste. Só o conjunto `dev` pode orientar mudanças no prompt.
"""

import json
from pathlib import Path
from typing import NamedTuple

MES = "2026-09-01"
OUTPUT = Path(__file__).parent / "sql.jsonl"

CITIES = [
    ("Anápolis", "GO"),
    ("Catalão", "GO"),
    ("Uberlândia", "MG"),
    ("Campinas", "SP"),
    ("Londrina", "PR"),
    ("Caruaru", "PE"),
    ("Feira de Santana", "BA"),
    ("Palmas", "TO"),
    ("Cuiabá", "MT"),
    ("Joinville", "SC"),
    ("Sobral", "CE"),
    ("Santarém", "PA"),
]
STATES = [
    ("Goiás", "GO", "de Goiás", "em Goiás"),
    ("Minas Gerais", "MG", "de Minas Gerais", "em Minas Gerais"),
    ("Bahia", "BA", "da Bahia", "na Bahia"),
    ("Santa Catarina", "SC", "de Santa Catarina", "em Santa Catarina"),
    ("Pernambuco", "PE", "de Pernambuco", "em Pernambuco"),
    ("Pará", "PA", "do Pará", "no Pará"),
]
REGIONS = ["Centro-Oeste", "Nordeste", "Sul"]
GROUPS = ["BRASIL TECPAR", "TELEFONICA", "VERO"]


class Template(NamedTuple):
    difficulty: str
    question: str
    sql: str
    kind: str  # cidade, estado, regiao, grupo, cidade_grupo ou fixo
    ordered: bool = False


CITY = "municipio = '{c}' AND uf = '{u}'"
M = f"mes_referencia = '{MES}'"
V = "semantic."

TEMPLATES = [
    Template(
        "facil",
        "Quantos acessos de banda larga existem em {c}?",
        f"SELECT acessos FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Qual é o HHI de {c}?",
        f"SELECT hhi FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Quantos provedores atuam em {c}?",
        f"SELECT provedores FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Qual é o nível de concentração do mercado de {c}?",
        f"SELECT nivel_concentracao FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Quem lidera o mercado de banda larga em {c}?",
        f"SELECT lider FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Qual é a população de {c}?",
        f"SELECT populacao FROM {V}municipios WHERE {CITY}",
        "cidade",
    ),
    Template(
        "facil",
        "Qual é a penetração por domicílio em {c}?",
        f"SELECT penetracao_domicilios FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Quanto cresceram os acessos de {c} nos últimos 12 meses?",
        f"SELECT crescimento_12m_pct FROM {V}mercado_municipal WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "facil",
        "Qual é a renda per capita de {c}?",
        f"SELECT renda_per_capita FROM {V}municipios WHERE {CITY}",
        "cidade",
    ),
    Template(
        "facil",
        "Quantos acessos existem no estado {de}?",
        f"SELECT sum(acessos) FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M}",
        "estado",
    ),
    Template(
        "facil",
        "Quantos municípios tem {e}?",
        f"SELECT count(*) FROM {V}municipios WHERE uf = '{{u}}'",
        "estado",
    ),
    Template(
        "facil",
        "Quantos acessos de banda larga fixa tem o Brasil?",
        f"SELECT sum(acessos) FROM {V}mercado_municipal WHERE {M}",
        "fixo",
    ),
    Template(
        "facil",
        "Quantos municípios brasileiros têm mercado altamente concentrado?",
        f"SELECT count(*) FROM {V}mercado_municipal "
        f"WHERE {M} AND nivel_concentracao = 'altamente concentrado'",
        "fixo",
    ),
    Template(
        "media",
        "Quais são os 5 municípios {de} com mais acessos?",
        f"SELECT municipio FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "ORDER BY acessos DESC LIMIT 5",
        "estado",
        ordered=True,
    ),
    Template(
        "media",
        "Quais são os 3 maiores provedores de {c} e seus market shares?",
        f"SELECT agente_nome, market_share_pct FROM {V}participacao_provedores "
        f"WHERE {CITY} AND {M} ORDER BY posicao, agente_nome LIMIT 3",
        "cidade",
        ordered=True,
    ),
    Template(
        "media",
        "Quantos acessos por fibra existem {em}?",
        f"SELECT sum(acessos) FROM {V}acessos_mensais "
        f"WHERE uf = '{{u}}' AND {M} AND meio_acesso = 'Fibra'",
        "estado",
    ),
    Template(
        "media",
        "Que percentual dos acessos de {c} é por fibra?",
        "SELECT round(100.0 * sum(acessos) FILTER (WHERE meio_acesso = 'Fibra') "
        f"/ sum(acessos), 2) FROM {V}acessos_mensais WHERE {CITY} AND {M}",
        "cidade",
    ),
    Template(
        "media",
        "Quantos municípios {de} têm mercado altamente concentrado?",
        f"SELECT count(*) FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "AND nivel_concentracao = 'altamente concentrado'",
        "estado",
    ),
    Template(
        "media",
        "Quais cidades {de} com mais de 100 mil habitantes têm mercado pouco disputado?",
        f"SELECT municipio FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "AND populacao > 100000 AND nivel_concentracao = 'altamente concentrado'",
        "estado",
    ),
    Template(
        "media",
        "Quais cidades {de} com mais de 100 mil habitantes têm o mercado mais disputado, "
        "sem concentração?",
        f"SELECT municipio FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "AND populacao > 100000 AND nivel_concentracao = 'não concentrado'",
        "estado",
    ),
    Template(
        "media",
        "Quantos acessos {c} tinha em dezembro de 2022?",
        f"SELECT acessos FROM {V}mercado_municipal WHERE {CITY} AND mes_referencia = '2022-12-01'",
        "cidade",
    ),
    Template(
        "media",
        "Quantos acessos o grupo {g} tem no Brasil?",
        f"SELECT sum(acessos) FROM {V}participacao_provedores WHERE agente_nome = '{{g}}' AND {M}",
        "grupo",
    ),
    Template(
        "media",
        "Quantos acessos de pessoas físicas existem {em}?",
        f"SELECT sum(acessos_pessoa_fisica) FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M}",
        "estado",
    ),
    Template(
        "media",
        "Qual é a faixa de velocidade com mais acessos em {c}?",
        f"SELECT faixa_velocidade FROM {V}velocidade_municipal WHERE {CITY} AND {M} "
        "ORDER BY acessos DESC LIMIT 1",
        "cidade",
    ),
    Template(
        "media",
        "Em quantos municípios o grupo {g} é o líder?",
        f"SELECT count(*) FROM {V}mercado_municipal WHERE lider = '{{g}}' AND {M}",
        "grupo",
    ),
    Template(
        "dificil",
        "Quais 5 grupos econômicos mais ganharam acessos no {r} desde janeiro de 2022?",
        "WITH a AS (SELECT agente_nome, "
        "sum(acessos) FILTER (WHERE mes_referencia = '2022-01-01') AS inicio, "
        f"sum(acessos) FILTER (WHERE {M}) AS fim FROM {V}acessos_mensais WHERE regiao = '{{r}}' "
        f"AND mes_referencia IN ('2022-01-01', '{MES}') GROUP BY agente_nome) "
        "SELECT agente_nome FROM a WHERE fim IS NOT NULL "
        "ORDER BY fim - coalesce(inicio, 0) DESC LIMIT 5",
        "regiao",
        ordered=True,
    ),
    Template(
        "dificil",
        "Entre os municípios {de} com mais de 100 mil habitantes, quais 3 mais cresceram "
        "em acessos nos últimos 12 meses?",
        f"SELECT municipio FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "AND populacao > 100000 AND crescimento_12m_pct IS NOT NULL "
        "ORDER BY crescimento_12m_pct DESC LIMIT 3",
        "estado",
        ordered=True,
    ),
    Template(
        "dificil",
        "Quantos acessos {e} ganhou entre setembro de 2024 e setembro de 2026?",
        f"SELECT sum(acessos) FILTER (WHERE {M}) - "
        "sum(acessos) FILTER (WHERE mes_referencia = '2024-09-01') "
        f"FROM {V}mercado_municipal WHERE uf = '{{u}}'",
        "estado",
    ),
    Template(
        "dificil",
        "Qual UF tem a maior penetração por domicílio, considerando o total de acessos e de "
        "domicílios do estado?",
        f"SELECT uf FROM {V}mercado_municipal WHERE {M} GROUP BY uf "
        "ORDER BY sum(acessos)::numeric / sum(domicilios) DESC LIMIT 1",
        "fixo",
    ),
    Template(
        "dificil",
        "Qual é a renda per capita média dos municípios altamente concentrados {de}?",
        f"SELECT round(avg(renda_per_capita)::numeric, 2) FROM {V}mercado_municipal "
        f"WHERE uf = '{{u}}' AND {M} AND nivel_concentracao = 'altamente concentrado'",
        "estado",
    ),
    Template(
        "dificil",
        "Quais municípios {de} têm renda per capita acima de R$ 1.500 e penetração por "
        "domicílio abaixo de 60?",
        f"SELECT municipio FROM {V}mercado_municipal WHERE uf = '{{u}}' AND {M} "
        "AND renda_per_capita > 1500 AND penetracao_domicilios < 60",
        "estado",
    ),
    Template(
        "dificil",
        "Que percentual dos acessos do Brasil está com os 3 maiores agentes econômicos?",
        "WITH a AS (SELECT agente_nome, sum(acessos) AS acessos "
        f"FROM {V}participacao_provedores WHERE {M} GROUP BY agente_nome) "
        "SELECT round(100.0 * (SELECT sum(acessos) FROM "
        "(SELECT acessos FROM a ORDER BY acessos DESC LIMIT 3) t) / sum(acessos), 2) FROM a",
        "fixo",
    ),
    Template(
        "dificil",
        "Como os acessos do {r} se dividem por meio de acesso?",
        f"SELECT meio_acesso, sum(acessos) FROM {V}acessos_mensais "
        f"WHERE regiao = '{{r}}' AND {M} GROUP BY meio_acesso",
        "regiao",
    ),
    Template(
        "dificil",
        "Em que mês {c} teve o maior número de acessos?",
        f"SELECT mes_referencia FROM {V}mercado_municipal WHERE {CITY} "
        "ORDER BY acessos DESC LIMIT 1",
        "cidade",
    ),
    Template(
        "dificil",
        "Quantos provedores de {c} perderam acessos entre setembro de 2025 e setembro de 2026?",
        "WITH a AS (SELECT agente_economico, "
        f"sum(acessos) FILTER (WHERE {M}) AS fim, "
        "sum(acessos) FILTER (WHERE mes_referencia = '2025-09-01') AS inicio "
        f"FROM {V}participacao_provedores WHERE {CITY} "
        f"AND mes_referencia IN ('2025-09-01', '{MES}') GROUP BY agente_economico) "
        "SELECT count(*) FROM a WHERE inicio > coalesce(fim, 0)",
        "cidade",
    ),
    Template(
        "dificil",
        "Que percentual dos acessos {de} está na faixa acima de 34 Mbps?",
        "SELECT round(100.0 * sum(acessos) FILTER (WHERE faixa_velocidade = '> 34Mbps') "
        f"/ sum(acessos), 2) FROM {V}velocidade_municipal WHERE uf = '{{u}}' AND {M}",
        "estado",
    ),
    Template(
        "dificil",
        "Em quantos municípios {de} o líder mudou entre setembro de 2023 e setembro de 2026?",
        f"SELECT count(*) FROM {V}mercado_municipal a JOIN {V}mercado_municipal b "
        "USING (municipio_ibge) WHERE a.uf = '{u}' AND a.mes_referencia = '2023-09-01' "
        f"AND b.mes_referencia = '{MES}' AND a.lider <> b.lider",
        "estado",
    ),
]


def expand(template: Template, index: int) -> list[dict[str, str]]:
    """Escolhe 3 parâmetros de cada lista, variando o ponto de partida por modelo."""

    def pick[T](values: list[T]) -> list[T]:
        step = len(values) // 3
        return [values[(index + offset * step) % len(values)] for offset in range(3)]

    if template.kind == "cidade":
        return [{"c": city, "u": uf} for city, uf in pick(CITIES)]
    if template.kind == "estado":
        return [{"e": name, "u": uf, "de": de, "em": em} for name, uf, de, em in pick(STATES)]
    if template.kind == "regiao":
        return [{"r": region} for region in REGIONS]
    if template.kind == "grupo":
        return [{"g": group} for group in GROUPS]
    return [{}]


def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    seen: dict[str, int] = {}
    for index, template in enumerate(TEMPLATES):
        position = seen.get(template.difficulty, 0)
        seen[template.difficulty] = position + 1
        split = "dev" if position % 2 == 0 else "test"
        for params in expand(template, index):
            cases.append(
                {
                    "id": f"{template.difficulty}-{index:02d}-{len(cases):03d}",
                    "template": index,
                    "split": split,
                    "difficulty": template.difficulty,
                    "question": template.question.format(**params),
                    "sql": template.sql.format(**params),
                    "ordered": template.ordered,
                }
            )
    return cases


if __name__ == "__main__":
    lines = [json.dumps(case, ensure_ascii=False) for case in build()]
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} casos em {OUTPUT}")
