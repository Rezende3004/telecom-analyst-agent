"""Recorte de telecom da base do CNPJ, com minimização de dados pessoais.

O recorte junta os estabelecimentos com CNAE de telecom e todos os CNPJs que declaram
acessos à Anatel. Contatos e endereços ficam de fora, e CPFs embutidos na razão social
de MEIs são removidos: nada disso é necessário, e o agente é público.
"""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO, cast

import duckdb
import pandera.errors
import polars as pl

from telecom_analyst.config import Settings
from telecom_analyst.etl.duck import connect
from telecom_analyst.ingest import anatel, receita
from telecom_analyst.ingest.contracts import EmpresaTelecom, EstabelecimentoTelecom, SocioTelecom

logger = logging.getLogger(__name__)

TELECOM_CNAES = (
    "6110801",  # telefonia fixa comutada
    "6110802",  # redes de longa distância
    "6110803",  # comunicação multimídia (SCM)
    "6110899",  # telecomunicações por fio, outros
    "6120501",  # telefonia móvel celular
    "6120502",  # serviço móvel especializado
    "6120599",  # telecomunicações sem fio, outros
    "6130200",  # telecomunicações por satélite
    "6141800",  # TV a cabo
    "6142600",  # TV por micro-ondas
    "6143400",  # TV por satélite
    "6190601",  # provedores de acesso à internet
    "6190602",  # provedores de voz sobre IP
    "6190699",  # outras atividades de telecomunicações
)
CPF_IN_NAME = r"\d{11}"
CHUNK_SIZE = 1024 * 1024
# A Receita publica em latin-1 com alguns bytes de controle soltos, como 0x1A e 0x8F.
CONTROL_BYTES = bytes([*range(9), 11, 12, *range(14, 32), *range(0x80, 0xA0)])
CLEAN_CONTROL_BYTES = bytes.maketrans(CONTROL_BYTES, b" " * len(CONTROL_BYTES))
EMPRESAS_COLUMNS = (
    "cnpj_basico",
    "razao_social",
    "natureza_juridica",
    "qualificacao_responsavel",
    "capital_social",
    "porte_empresa",
    "ente_federativo",
)
ESTABELECIMENTOS_COLUMNS = (
    "cnpj_basico",
    "cnpj_ordem",
    "cnpj_dv",
    "identificador_matriz_filial",
    "nome_fantasia",
    "situacao_cadastral",
    "data_situacao_cadastral",
    "motivo_situacao_cadastral",
    "nome_cidade_exterior",
    "pais",
    "data_inicio_atividade",
    "cnae_principal",
    "cnae_secundaria",
    "tipo_logradouro",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "uf",
    "municipio_tom",
    "ddd_1",
    "telefone_1",
    "ddd_2",
    "telefone_2",
    "ddd_fax",
    "fax",
    "correio_eletronico",
    "situacao_especial",
    "data_situacao_especial",
)
SOCIOS_COLUMNS = (
    "cnpj_basico",
    "identificador_socio",
    "nome_socio",
    "cnpj_cpf_socio",
    "qualificacao_socio",
    "data_entrada_sociedade",
    "pais",
    "representante_legal",
    "nome_representante",
    "qualificacao_representante",
    "faixa_etaria",
)
LOOKUP_COLUMNS = ("codigo", "descricao")


def staging_dir(settings: Settings, month: str) -> Path:
    return settings.data_dir / "staging" / "receita" / month


def csv_dir(settings: Settings, month: str) -> Path:
    return settings.data_dir / "staging" / "receita" / f"{month}.csv"


def transcode(source: BinaryIO, target: BinaryIO) -> None:
    """Copia de latin-1 para UTF-8, trocando bytes de controle por espaço."""
    while chunk := source.read(CHUNK_SIZE):
        target.write(chunk.translate(CLEAN_CONTROL_BYTES).decode("latin-1").encode("utf-8"))


def extract_csvs(settings: Settings, month: str) -> Path:
    """Descompacta os arquivos do mês em um diretório por tabela, já em UTF-8."""
    source = receita.raw_dir(settings, month)
    target = csv_dir(settings, month)
    for name in sorted(receita.REQUIRED_FILES):
        table = name.removesuffix(".zip").rstrip("0123456789").lower()
        (target / table).mkdir(parents=True, exist_ok=True)
        output = target / table / f"{name.removesuffix('.zip')}.csv"
        if output.exists():
            continue
        partial = output.with_suffix(".part")
        with zipfile.ZipFile(source / name) as archive, partial.open("wb") as stream:
            members = archive.namelist()
            if len(members) != 1:
                raise ValueError(f"{name}: esperava um arquivo, encontrou {members}")
            with archive.open(members[0]) as member:
                transcode(cast(BinaryIO, member), stream)
        partial.replace(output)
    return target


def _reader(directory: Path, columns: tuple[str, ...]) -> str:
    types = ", ".join(f"'{column}': 'VARCHAR'" for column in columns)
    return f"""read_csv(
        '{directory}/*.csv', delim = ';', quote = '"', escape = '"', header = false,
        columns = {{{types}}}, strict_mode = false
    )"""


def _date(column: str) -> str:
    return f"try_strptime({column}, '%Y%m%d')::DATE AS {column}"


def build_views(connection: duckdb.DuckDBPyConnection, csvs: Path, provider_cnpjs: Path) -> None:
    """Cria as views do recorte. É a mesma lógica do benchmark com Spark."""
    cnaes = ", ".join(f"'{cnae}'" for cnae in TELECOM_CNAES)
    connection.execute(f"""
        CREATE OR REPLACE VIEW raw_estabelecimentos AS
        SELECT * FROM {_reader(csvs / "estabelecimentos", ESTABELECIMENTOS_COLUMNS)}
    """)  # noqa: S608
    connection.execute(f"""
        CREATE OR REPLACE TEMP TABLE alvo AS
        SELECT DISTINCT cnpj_basico
        FROM raw_estabelecimentos
        WHERE cnae_principal IN ({cnaes})
           OR list_has_any(string_split(cnae_secundaria, ','), [{cnaes}])
        UNION
        SELECT DISTINCT left(cnpj, 8) FROM read_parquet('{provider_cnpjs}/*/*.parquet')
    """)  # noqa: S608
    connection.execute(f"""
        CREATE OR REPLACE VIEW estabelecimentos AS
        SELECT
            cnpj_basico || cnpj_ordem || cnpj_dv AS cnpj,
            cnpj_basico,
            identificador_matriz_filial = '1' AS matriz,
            regexp_replace(nome_fantasia, '{CPF_IN_NAME}', '', 'g') AS nome_fantasia,
            situacao_cadastral,
            {_date("data_situacao_cadastral")},
            motivo_situacao_cadastral,
            {_date("data_inicio_atividade")},
            cnae_principal,
            cnae_secundaria,
            uf,
            municipio_tom
        FROM raw_estabelecimentos
        SEMI JOIN alvo USING (cnpj_basico)
    """)  # noqa: S608
    connection.execute(f"""
        CREATE OR REPLACE VIEW empresas AS
        SELECT
            cnpj_basico,
            trim(regexp_replace(razao_social, '{CPF_IN_NAME}', '', 'g')) AS razao_social,
            natureza_juridica,
            CAST(replace(capital_social, ',', '.') AS DOUBLE) AS capital_social,
            porte_empresa
        FROM {_reader(csvs / "empresas", EMPRESAS_COLUMNS)}
        SEMI JOIN alvo USING (cnpj_basico)
    """)  # noqa: S608
    connection.execute(f"""
        CREATE OR REPLACE VIEW socios AS
        SELECT
            cnpj_basico,
            identificador_socio,
            nome_socio,
            cnpj_cpf_socio,
            qualificacao_socio,
            {_date("data_entrada_sociedade")}
        FROM {_reader(csvs / "socios", SOCIOS_COLUMNS)}
        SEMI JOIN alvo USING (cnpj_basico)
    """)  # noqa: S608


def write_tables(connection: duckdb.DuckDBPyConnection, csvs: Path, target: Path) -> None:
    connection.execute(f"""
        COPY estabelecimentos TO '{target}/estabelecimentos' (
            FORMAT parquet, PARTITION_BY (uf), WRITE_PARTITION_COLUMNS true, COMPRESSION zstd
        )
    """)
    for table in ("empresas", "socios"):
        connection.execute(
            f"COPY {table} TO '{target}/{table}.parquet' (FORMAT parquet, COMPRESSION zstd)"
        )
    for table in ("cnaes", "motivos", "municipios", "naturezas", "qualificacoes"):
        reader = _reader(csvs / table, LOOKUP_COLUMNS)
        connection.execute(
            f"COPY (SELECT * FROM {reader}) TO '{target}/{table}.parquet' "  # noqa: S608
            "(FORMAT parquet, COMPRESSION zstd)"
        )


def validate(directory: Path) -> dict[str, int]:
    tables = {
        "empresas": (EmpresaTelecom, directory / "empresas.parquet"),
        "socios": (SocioTelecom, directory / "socios.parquet"),
        "estabelecimentos": (
            EstabelecimentoTelecom,
            directory / "estabelecimentos" / "*" / "*.parquet",
        ),
    }
    rows = {}
    for name, (contract, path) in tables.items():
        frame = pl.read_parquet(path, hive_partitioning=False)
        try:
            contract.validate(frame, lazy=True)
        except pandera.errors.SchemaErrors as error:
            raise ValueError(f"{name}: contrato violado\n{error}") from error
        rows[name] = frame.height
    return rows


def build_staging(settings: Settings, month: str, *, keep_csvs: bool = False) -> dict[str, int]:
    csvs = extract_csvs(settings, month)
    target = staging_dir(settings, month)
    next_target = target.with_name(f"{target.name}.next")
    shutil.rmtree(next_target, ignore_errors=True)
    next_target.mkdir(parents=True)

    connection = connect(settings)
    build_views(connection, csvs, anatel.staging_dir(settings) / "acessos")
    write_tables(connection, csvs, next_target)

    rows = validate(next_target)
    shutil.rmtree(target, ignore_errors=True)
    next_target.replace(target)
    if not keep_csvs:
        shutil.rmtree(csvs)
    logger.info("cnpj %s: %s", month, rows)
    return rows
