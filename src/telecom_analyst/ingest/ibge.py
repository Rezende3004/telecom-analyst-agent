"""Municípios e indicadores do IBGE, unidos em uma tabela por código de município."""

import json
import logging
from pathlib import Path
from typing import Any, NamedTuple

import httpx
import polars as pl

from telecom_analyst.config import Settings
from telecom_analyst.ingest.contracts import Municipio
from telecom_analyst.ingest.download import Manifest, fetch

logger = logging.getLogger(__name__)

LOCALIDADES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
AGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
MUNICIPIOS_FILE = "municipios.json"


class Indicator(NamedTuple):
    name: str
    aggregate: int
    variable: int


INDICATORS = (
    Indicator("populacao", aggregate=6579, variable=9324),  # estimativa anual
    Indicator("domicilios", aggregate=4712, variable=381),  # Censo 2022
    Indicator("pib_mil_reais", aggregate=5938, variable=37),  # PIB dos Municípios
    Indicator("renda_per_capita", aggregate=10295, variable=13431),  # Censo 2022
)


def raw_dir(settings: Settings) -> Path:
    return settings.data_dir / "raw" / "ibge"


def staging_path(settings: Settings) -> Path:
    return settings.data_dir / "staging" / "ibge" / "municipios.parquet"


def indicator_url(indicator: Indicator) -> str:
    return (
        f"{AGREGADOS_URL}/{indicator.aggregate}/periodos/-1/variaveis/{indicator.variable}"
        "?localidades=N6[all]"
    )


def download(settings: Settings, client: httpx.Client) -> None:
    directory = raw_dir(settings)
    fetch(client, LOCALIDADES_URL, directory, MUNICIPIOS_FILE)
    for indicator in INDICATORS:
        fetch(client, indicator_url(indicator), directory, f"{indicator.name}.json")


def parse_value(value: str | None) -> float | None:
    """Converte o valor do SIDRA. Códigos como '-', '...' e 'X' indicam dado ausente."""
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def parse_indicator(payload: list[dict[str, Any]], name: str) -> pl.DataFrame:
    """Transforma a resposta da API de agregados em municipio_ibge, valor e ano."""
    rows = [
        {"municipio_ibge": item["localidade"]["id"], name: parse_value(value), f"{name}_ano": year}
        for result in payload[0]["resultados"]
        for item in result["series"]
        for year, value in item["serie"].items()
    ]
    schema = {"municipio_ibge": pl.String, name: pl.Float64, f"{name}_ano": pl.String}
    return pl.DataFrame(rows, schema=schema)


def parse_municipios(payload: list[dict[str, Any]]) -> pl.DataFrame:
    rows = [
        {
            "municipio_ibge": str(item["municipio-id"]),
            "municipio": item["municipio-nome"],
            "uf": item["UF-sigla"],
            "uf_nome": item["UF-nome"],
            "regiao": item["regiao-nome"],
        }
        for item in payload
    ]
    return pl.DataFrame(rows)


def _read_json(path: Path) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads(path.read_text())
    return payload


def build_table(directory: Path) -> pl.DataFrame:
    table = parse_municipios(_read_json(directory / MUNICIPIOS_FILE))
    for indicator in INDICATORS:
        parsed = parse_indicator(_read_json(directory / f"{indicator.name}.json"), indicator.name)
        table = table.join(parsed, on="municipio_ibge", how="left", validate="1:1")

    return table.with_columns(
        pl.col("populacao", "domicilios").cast(pl.Int64),
        pl.col("populacao_ano", "domicilios_ano", "pib_mil_reais_ano", "renda_per_capita_ano")
        .cast(pl.Int64)
        .fill_null(strategy="max"),
    ).rename({"pib_mil_reais_ano": "pib_ano", "renda_per_capita_ano": "renda_ano"})


def build_staging(settings: Settings) -> str:
    """Grava a tabela validada e devolve o período de cada indicador."""
    directory = raw_dir(settings)
    table = build_table(directory)
    Municipio.validate(table, lazy=True)

    target = staging_path(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    table.write_parquet(target, compression="zstd")

    first = table.row(0, named=True)
    period = " ".join(
        f"{name}={first[f'{name}_ano']}" for name in ("populacao", "domicilios", "pib", "renda")
    )
    manifest = Manifest.load(directory)
    manifest.reference_period = period
    manifest.save(directory)
    logger.info("ibge: %d municípios (%s)", table.height, period)
    return period
