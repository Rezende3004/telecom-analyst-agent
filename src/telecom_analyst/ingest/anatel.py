"""Acessos de banda larga fixa da Anatel: download, staging em Parquet e conciliação."""

import logging
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import duckdb
import httpx
import pandera.errors
import polars as pl

from telecom_analyst.config import Settings
from telecom_analyst.etl.duck import connect
from telecom_analyst.ingest.contracts import Acessos, Densidade, TotalMensal
from telecom_analyst.ingest.download import FileRecord, Manifest, fetch

logger = logging.getLogger(__name__)

ACESSOS_URL = (
    "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/acessos/acessos_banda_larga_fixa.zip"
)
ARCHIVE_NAME = "acessos_banda_larga_fixa.zip"
LONG_CSV = re.compile(r"Acessos_Banda_Larga_Fixa_\d{4}(-\d{4})?\.csv")
TOTAL_CSV = "Acessos_Banda_Larga_Fixa_Total.csv"
DENSITY_CSV = "Densidade_Banda_Larga_Fixa.csv"

LAYOUT_UNTIL_2020 = (
    "Ano",
    "Mês",
    "Grupo Econômico",
    "Empresa",
    "CNPJ",
    "Porte da Prestadora",
    "UF",
    "Município",
    "Código IBGE Município",
    "Faixa de Velocidade",
    "Tecnologia",
    "Meio de Acesso",
    "Acessos",
)
LAYOUT_SINCE_2021 = (
    *LAYOUT_UNTIL_2020[:10],
    "Velocidade",
    "Tecnologia",
    "Meio de Acesso",
    "Tipo de Pessoa",
    "Tipo de Produto",
    "Acessos",
)


class LayoutError(ValueError):
    """Um CSV da Anatel chegou com colunas que o pipeline não conhece."""


class ReconciliationError(ValueError):
    """A soma das linhas não bate com o total oficial publicado."""


def raw_dir(settings: Settings) -> Path:
    return settings.data_dir / "raw" / "anatel"


def staging_dir(settings: Settings) -> Path:
    return settings.data_dir / "staging" / "anatel"


def download(settings: Settings, client: httpx.Client) -> FileRecord:
    return fetch(client, ACESSOS_URL, raw_dir(settings), ARCHIVE_NAME)


def _header(archive: zipfile.ZipFile, name: str) -> tuple[str, ...]:
    with archive.open(name) as stream:
        line = stream.readline().decode("utf-8-sig").strip()
    return tuple(line.split(";"))


def check_layouts(archive: zipfile.ZipFile) -> list[str]:
    """Devolve os CSVs longos do zip e falha se algum tiver um layout desconhecido."""
    names = sorted(name for name in archive.namelist() if LONG_CSV.fullmatch(name))
    if not names:
        raise LayoutError("nenhum CSV longo de acessos encontrado no zip")
    for name in names:
        header = _header(archive, name)
        if header not in (LAYOUT_UNTIL_2020, LAYOUT_SINCE_2021):
            raise LayoutError(f"{name}: layout desconhecido: {header}")
    return names


def _extract(archive: zipfile.ZipFile, names: list[str], directory: Path) -> None:
    for name in names:
        with archive.open(name) as source, (directory / Path(name).name).open("wb") as target:
            shutil.copyfileobj(source, target)


def _write_acessos(connection: duckdb.DuckDBPyConnection, source_glob: Path, target: Path) -> None:
    query = f"""
        COPY (
            SELECT
                CAST("Ano" AS SMALLINT) AS ano,
                CAST("Mês" AS TINYINT) AS mes,
                "Grupo Econômico" AS grupo_economico,
                "Empresa" AS empresa,
                "CNPJ" AS cnpj,
                "Porte da Prestadora" AS porte,
                "UF" AS uf,
                "Município" AS municipio,
                "Código IBGE Município" AS municipio_ibge,
                "Faixa de Velocidade" AS faixa_velocidade,
                CAST(replace("Velocidade", ',', '.') AS DOUBLE) AS velocidade_mbps,
                "Tecnologia" AS tecnologia,
                "Meio de Acesso" AS meio_acesso,
                "Tipo de Pessoa" AS tipo_pessoa,
                "Tipo de Produto" AS tipo_produto,
                CAST("Acessos" AS BIGINT) AS acessos
            FROM read_csv(
                '{source_glob}', delim = ';', header = true, all_varchar = true,
                union_by_name = true, strict_mode = true
            )
        ) TO '{target}' (
            FORMAT parquet, PARTITION_BY (ano), WRITE_PARTITION_COLUMNS true, COMPRESSION zstd
        )
    """  # noqa: S608
    connection.execute(query)


def _write_total(connection: duckdb.DuckDBPyConnection, source: Path, target: Path) -> None:
    query = f"""
        COPY (
            SELECT
                CAST("Ano" AS SMALLINT) AS ano,
                CAST("Mês" AS TINYINT) AS mes,
                CAST("Acessos" AS BIGINT) AS acessos
            FROM read_csv('{source}', delim = ';', header = true, all_varchar = true)
        ) TO '{target}' (FORMAT parquet, COMPRESSION zstd)
    """  # noqa: S608
    connection.execute(query)


def _write_density(connection: duckdb.DuckDBPyConnection, source: Path, target: Path) -> None:
    query = f"""
        COPY (
            SELECT
                CAST("Ano" AS SMALLINT) AS ano,
                CAST("Mês" AS TINYINT) AS mes,
                "UF" AS uf,
                "Município" AS municipio,
                "Código IBGE" AS municipio_ibge,
                CAST(replace("Densidade", ',', '.') AS DOUBLE) AS densidade,
                "Nível Geográfico Densidade" AS nivel_geografico
            FROM read_csv('{source}', delim = ';', header = true, all_varchar = true)
            WHERE "Código IBGE" IS NOT NULL
        ) TO '{target}' (FORMAT parquet, COMPRESSION zstd)
    """  # noqa: S608
    connection.execute(query)


def validate_acessos(directory: Path) -> int:
    """Valida o contrato ano a ano, para não carregar toda a série na memória."""
    rows = 0
    for partition in sorted(directory.glob("ano=*")):
        frame = pl.read_parquet(partition / "*.parquet", hive_partitioning=False)
        try:
            Acessos.validate(frame, lazy=True)
        except pandera.errors.SchemaErrors as error:
            raise ValueError(f"{partition.name}: contrato violado\n{error}") from error
        rows += frame.height
        logger.info("%s: %d linhas válidas", partition.name, frame.height)
    return rows


def reconcile(connection: duckdb.DuckDBPyConnection, directory: Path) -> int:
    """Confere cada mês contra o total oficial e devolve quantos meses foram conferidos."""
    query = f"""
        SELECT
            coalesce(soma.ano, total.ano) AS ano,
            coalesce(soma.mes, total.mes) AS mes,
            soma.acessos AS soma,
            total.acessos AS oficial
        FROM (
            SELECT ano, mes, sum(acessos) AS acessos
            FROM read_parquet('{directory}/acessos/*/*.parquet')
            GROUP BY ano, mes
        ) AS soma
        FULL JOIN read_parquet('{directory}/total_mensal.parquet') AS total
            USING (ano, mes)
        ORDER BY ano, mes
    """  # noqa: S608
    rows = connection.execute(query).fetchall()
    divergent = [row for row in rows if row[2] != row[3]]
    if divergent:
        raise ReconciliationError(f"{len(divergent)} meses divergem do total: {divergent[:5]}")
    return len(rows)


def build_staging(settings: Settings) -> str:
    """Converte o zip em Parquet validado e devolve o último mês disponível (AAAA-MM)."""
    target = staging_dir(settings)
    next_target = target.with_name(f"{target.name}.next")
    shutil.rmtree(next_target, ignore_errors=True)
    next_target.mkdir(parents=True)

    with (
        zipfile.ZipFile(raw_dir(settings) / ARCHIVE_NAME) as archive,
        tempfile.TemporaryDirectory(dir=next_target) as extracted,
    ):
        names = check_layouts(archive)
        _extract(archive, [*names, TOTAL_CSV, DENSITY_CSV], Path(extracted))
        connection = connect(settings)
        csvs = Path(extracted)
        _write_acessos(
            connection,
            csvs / "Acessos_Banda_Larga_Fixa_[0-9]*.csv",
            next_target / "acessos",
        )
        _write_total(connection, csvs / TOTAL_CSV, next_target / "total_mensal.parquet")
        _write_density(connection, csvs / DENSITY_CSV, next_target / "densidade.parquet")

    TotalMensal.validate(pl.read_parquet(next_target / "total_mensal.parquet"), lazy=True)
    Densidade.validate(pl.read_parquet(next_target / "densidade.parquet"), lazy=True)
    rows = validate_acessos(next_target / "acessos")
    months = reconcile(connection, next_target)
    logger.info("anatel: %d linhas, %d meses iguais ao total oficial", rows, months)

    shutil.rmtree(target, ignore_errors=True)
    next_target.replace(target)

    last = pl.read_parquet(target / "total_mensal.parquet").sort("ano", "mes").row(-1, named=True)
    period = f"{last['ano']}-{last['mes']:02d}"

    manifest = Manifest.load(raw_dir(settings))
    manifest.reference_period = period
    manifest.save(raw_dir(settings))
    return period
