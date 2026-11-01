import io
from pathlib import Path

import pandera.errors
import polars as pl
import pytest

from telecom_analyst.config import Settings
from telecom_analyst.etl import cnpj
from telecom_analyst.etl.duck import connect
from telecom_analyst.ingest.contracts import EmpresaTelecom
from tests.factories import make_settings

ISP = "11111111"
ANATEL_ONLY = "22222222"
MEI_ISP = "33333333"
BAKERY = "44444444"
FAKE_CPF = "12345678901"


def establishment(basico: str, cnae: str, secondary: str = "", fantasia: str = "") -> str:
    fields = [
        basico,
        "0001",
        "00",
        "1",
        fantasia,
        "02",
        "20200101",
        "00",
        "",
        "",
        "20100315",
        cnae,
        secondary,
        "RUA",
        "RUA SECRETA",
        "1",
        "",
        "CENTRO",
        "74000000",
        "GO",
        "9373",
        "62",
        "999999999",
        "",
        "",
        "",
        "",
        "pessoa@example.test",
        "",
        "",
    ]
    return ";".join(f'"{field}"' for field in fields)


def write_csvs(directory: Path) -> None:
    for table in ("estabelecimentos", "empresas", "socios"):
        (directory / table).mkdir(parents=True)
    (directory / "estabelecimentos" / "part.csv").write_text(
        "\n".join(
            [
                establishment(ISP, "6110803"),
                establishment(ANATEL_ONLY, "4751201"),
                establishment(MEI_ISP, "4751201", secondary="9511800,6190601"),
                establishment(BAKERY, "1091101", fantasia=f"PADARIA {FAKE_CPF}"),
            ]
        )
        + "\n",
    )
    (directory / "empresas" / "part.csv").write_text(
        f'"{ISP}";"PROVEDOR LTDA";"2062";"49";"1000,50";"03";""\n'
        f'"{ANATEL_ONLY}";"REDE SA";"2054";"10";"0,00";"05";""\n'
        f'"{MEI_ISP}";"PESSOA INTERNET {FAKE_CPF}";"2135";"50";"100,00";"01";""\n'
        f'"{BAKERY}";"PADARIA LTDA";"2062";"49";"1,00";"01";""\n',
    )
    (directory / "socios" / "part.csv").write_text(
        f'"{ISP}";"2";"FULANA";"***123456**";"49";"20200101";"";"***000000**";"REPRESENTANTE";"00";"4"\n'
        f'"{BAKERY}";"2";"FULANO";"***654321**";"49";"20200101";"";"***000000**";"";"00";"4"\n',
    )


def write_providers(directory: Path) -> None:
    partition = directory / "ano=2026"
    partition.mkdir(parents=True)
    pl.DataFrame({"cnpj": [f"{ANATEL_ONLY}000100"]}).write_parquet(partition / "data.parquet")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(data_dir=tmp_path)


@pytest.fixture
def tables(settings: Settings, tmp_path: Path) -> dict[str, list[dict[str, object]]]:
    write_csvs(tmp_path / "csv")
    write_providers(tmp_path / "acessos")
    connection = connect(settings)
    cnpj.build_views(connection, tmp_path / "csv", tmp_path / "acessos")

    result = {}
    for table in ("estabelecimentos", "empresas", "socios"):
        cursor = connection.execute(f"SELECT * FROM {table}")  # noqa: S608
        columns = [column[0] for column in cursor.description]
        result[table] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return result


def test_transcode_converts_to_utf8_and_removes_control_bytes() -> None:
    source = io.BytesIO(b"Jo\xe3o\x1aSilva\x8f\n")
    target = io.BytesIO()

    cnpj.transcode(source, target)

    assert target.getvalue().decode("utf-8") == "João Silva \n"


def test_selects_telecom_cnae_in_any_position_and_anatel_providers(
    tables: dict[str, list[dict[str, object]]],
) -> None:
    selected = {row["cnpj_basico"] for row in tables["estabelecimentos"]}

    assert selected == {ISP, ANATEL_ONLY, MEI_ISP}


def test_only_selected_companies_keep_partners(
    tables: dict[str, list[dict[str, object]]],
) -> None:
    assert [row["cnpj_basico"] for row in tables["socios"]] == [ISP]


def test_removes_cpf_from_company_name(tables: dict[str, list[dict[str, object]]]) -> None:
    names = {row["cnpj_basico"]: row["razao_social"] for row in tables["empresas"]}

    assert names[MEI_ISP] == "PESSOA INTERNET"


def test_drops_contact_and_address_fields(tables: dict[str, list[dict[str, object]]]) -> None:
    columns = set(tables["estabelecimentos"][0])

    assert columns.isdisjoint(
        {"logradouro", "numero", "cep", "telefone_1", "correio_eletronico", "bairro"}
    )
    assert "pessoa@example.test" not in str(tables["estabelecimentos"])
    assert "REPRESENTANTE" not in str(tables["socios"])


def test_parses_brazilian_decimal_and_dates(
    tables: dict[str, list[dict[str, object]]],
) -> None:
    empresa = next(row for row in tables["empresas"] if row["cnpj_basico"] == ISP)
    estabelecimento = next(row for row in tables["estabelecimentos"] if row["cnpj_basico"] == ISP)

    assert empresa["capital_social"] == 1000.5
    assert str(estabelecimento["data_inicio_atividade"]) == "2010-03-15"


def test_contract_blocks_cpf_that_escaped_the_cleanup() -> None:
    frame = pl.DataFrame(
        {
            "cnpj_basico": [MEI_ISP],
            "razao_social": [f"PESSOA INTERNET {FAKE_CPF}"],
            "natureza_juridica": ["2135"],
            "capital_social": [100.0],
            "porte_empresa": ["01"],
        }
    )

    with pytest.raises(pandera.errors.SchemaErrors):
        EmpresaTelecom.validate(frame, lazy=True)


def test_contract_allows_short_numbers_in_company_name() -> None:
    frame = pl.DataFrame(
        {
            "cnpj_basico": [ISP],
            "razao_social": ["36.627.971 PROVEDOR 2000 LTDA"],
            "natureza_juridica": ["2062"],
            "capital_social": [100.0],
            "porte_empresa": ["03"],
        }
    )

    EmpresaTelecom.validate(frame, lazy=True)
