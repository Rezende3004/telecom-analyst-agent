from typing import Any

import pandera.errors
import polars as pl
import pytest

from telecom_analyst.ingest.contracts import MAX_LINHAS_SEM_CADASTRO, Acessos, Municipio

ACESSOS: dict[str, Any] = {
    "ano": 2026,
    "mes": 9,
    "grupo_economico": "OUTROS",
    "empresa": "Provedor",
    "cnpj": "76535764000143",
    "porte": "Pequeno Porte",
    "uf": "GO",
    "municipio": "Anápolis",
    "municipio_ibge": "5201108",
    "faixa_velocidade": "> 34Mbps",
    "velocidade_mbps": 100.0,
    "tecnologia": "FTTH",
    "meio_acesso": "Fibra",
    "tipo_pessoa": "Pessoa Física",
    "tipo_produto": "INTERNET",
    "acessos": 10,
}
ACESSOS_TYPES = {"ano": pl.Int16, "mes": pl.Int8}

MUNICIPIO: dict[str, Any] = {
    "municipio_ibge": "5201108",
    "municipio": "Anápolis",
    "uf": "GO",
    "uf_nome": "Goiás",
    "regiao": "Centro-Oeste",
    "populacao": 424647,
    "populacao_ano": 2026,
    "domicilios": 142329,
    "domicilios_ano": 2022,
    "pib_mil_reais": 1000.0,
    "pib_ano": 2023,
    "renda_per_capita": 2000.0,
    "renda_ano": 2022,
}


def acessos_frame(rows: int = 1, **overrides: Any) -> pl.DataFrame:
    row = ACESSOS | overrides
    frame = pl.DataFrame({key: [value] * rows for key, value in row.items()})
    return frame.with_columns(
        pl.col(name).cast(dtype) for name, dtype in ACESSOS_TYPES.items()
    ).with_columns(pl.col("empresa").cast(pl.String), pl.col("porte").cast(pl.String))


def test_accepts_valid_row() -> None:
    Acessos.validate(acessos_frame(), lazy=True)


def test_accepts_alphanumeric_cnpj() -> None:
    Acessos.validate(acessos_frame(cnpj="A1B2C3D4E5F6G7"), lazy=True)


def test_accepts_new_technology_without_changing_contract() -> None:
    Acessos.validate(acessos_frame(tecnologia="6G"), lazy=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"cnpj": "123"},
        {"municipio_ibge": "52011"},
        {"uf": "XX"},
        {"mes": 13},
        {"acessos": 0},
        {"meio_acesso": "Pombo-correio"},
        {"faixa_velocidade": "muito rápida"},
        {"velocidade_mbps": 0.0},
    ],
    ids=lambda overrides: next(iter(overrides)),
)
def test_rejects_invalid_values(overrides: dict[str, Any]) -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        Acessos.validate(acessos_frame(**overrides), lazy=True)


def test_rejects_unexpected_column() -> None:
    frame = acessos_frame().with_columns(pl.lit(1).alias("coluna_nova"))

    with pytest.raises(pandera.errors.SchemaErrors):
        Acessos.validate(frame, lazy=True)


def test_tolerates_few_rows_without_registry_data() -> None:
    frame = acessos_frame(empresa=None, grupo_economico="OUTROS", porte=None)

    Acessos.validate(frame, lazy=True)


def test_rejects_many_rows_without_registry_data() -> None:
    frame = acessos_frame(MAX_LINHAS_SEM_CADASTRO + 1, empresa=None)

    with pytest.raises(pandera.errors.SchemaErrors):
        Acessos.validate(frame, lazy=True)


def test_rejects_widespread_missing_census_data() -> None:
    rows = [
        MUNICIPIO | {"municipio_ibge": code, "domicilios": None} for code in ("5201108", "5208707")
    ]

    frame = pl.DataFrame(rows).with_columns(pl.col("domicilios").cast(pl.Int64))

    with pytest.raises(pandera.errors.SchemaErrors):
        Municipio.validate(frame, lazy=True)


def test_tolerates_municipality_created_after_census() -> None:
    rows = [MUNICIPIO, MUNICIPIO | {"municipio_ibge": "5101837", "domicilios": None}]

    Municipio.validate(pl.DataFrame(rows), lazy=True)


def test_rejects_duplicated_municipality() -> None:
    with pytest.raises(pandera.errors.SchemaErrors):
        Municipio.validate(pl.DataFrame([MUNICIPIO, MUNICIPIO]), lazy=True)
