import zipfile
from pathlib import Path

import polars as pl
import pytest

from telecom_analyst.config import Settings
from telecom_analyst.ingest import anatel
from telecom_analyst.ingest.download import Manifest
from tests.factories import make_settings

BOM = "﻿"
HEADER_2020 = ";".join(anatel.LAYOUT_UNTIL_2020)
HEADER_2021 = ";".join(anatel.LAYOUT_SINCE_2021)
ROW_2020 = (
    "2020;12;OI;OI;76535764000143;Grande Porte;GO;Anápolis;5201108;"
    "2Mbps a 12Mbps;xDSL;Cabo Metálico;10"
)
ROW_2021 = (
    "2021;1;OUTROS;Provedor;A1B2C3D4E5F6G7;Pequeno Porte;GO;Anápolis;5201108;"
    "2Mbps a 12Mbps;1,024000;FTTH;Fibra;Pessoa Física;INTERNET;5"
)
DENSITY = (
    "Ano;Mês;UF;Município;Código IBGE;Densidade;Nível Geográfico Densidade\n"
    "2021;1;GO;Anápolis;5201108;1,5;Municipio\n"
    "2021;1;;;;;Municipio\n"
)


def write_archive(settings: Settings, total_2021: int = 5) -> None:
    directory = anatel.raw_dir(settings)
    directory.mkdir(parents=True)
    contents = {
        "Acessos_Banda_Larga_Fixa_2019-2020.csv": f"{HEADER_2020}\n{ROW_2020}\n",
        "Acessos_Banda_Larga_Fixa_2019_2020_Colunas.csv": "CNPJ;2019-01\n1;1\n",
        "Acessos_Banda_Larga_Fixa_2021.csv": f"{HEADER_2021}\n{ROW_2021}\n",
        anatel.TOTAL_CSV: f"Ano;Mês;Acessos\n2020;12;10\n2021;1;{total_2021}\n",
        anatel.DENSITY_CSV: DENSITY,
    }
    with zipfile.ZipFile(directory / anatel.ARCHIVE_NAME, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, BOM + content)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(data_dir=tmp_path)


def test_build_staging_unifies_both_layouts(settings: Settings) -> None:
    write_archive(settings)

    period = anatel.build_staging(settings)

    acessos = pl.read_parquet(
        anatel.staging_dir(settings) / "acessos" / "*" / "*.parquet", hive_partitioning=False
    ).sort("ano")
    assert period == "2021-01"
    assert acessos["acessos"].to_list() == [10, 5]
    assert acessos["velocidade_mbps"].to_list() == [None, 1.024]
    assert acessos["tipo_pessoa"].to_list() == [None, "Pessoa Física"]
    assert Manifest.load(anatel.raw_dir(settings)).reference_period == "2021-01"


def test_build_staging_keeps_cnpj_as_text(settings: Settings) -> None:
    write_archive(settings)

    anatel.build_staging(settings)

    acessos = pl.read_parquet(
        anatel.staging_dir(settings) / "acessos" / "ano=2020" / "*.parquet",
        hive_partitioning=False,
    )
    assert acessos.schema["cnpj"] == pl.String
    assert acessos["cnpj"].to_list() == ["76535764000143"]


def test_build_staging_drops_empty_density_rows(settings: Settings) -> None:
    write_archive(settings)

    anatel.build_staging(settings)

    density = pl.read_parquet(anatel.staging_dir(settings) / "densidade.parquet")
    assert density["densidade"].to_list() == [1.5]


def test_divergence_from_official_total_stops_pipeline(settings: Settings) -> None:
    write_archive(settings, total_2021=6)

    with pytest.raises(anatel.ReconciliationError, match="1 meses divergem"):
        anatel.build_staging(settings)


def test_failed_run_keeps_previous_staging(settings: Settings) -> None:
    write_archive(settings)
    anatel.build_staging(settings)
    (anatel.raw_dir(settings) / anatel.ARCHIVE_NAME).unlink()
    with zipfile.ZipFile(anatel.raw_dir(settings) / anatel.ARCHIVE_NAME, "w") as archive:
        archive.writestr("Acessos_Banda_Larga_Fixa_2021.csv", f"{BOM}Ano;Mês;Coluna Nova\n")

    with pytest.raises(anatel.LayoutError):
        anatel.build_staging(settings)

    assert (anatel.staging_dir(settings) / "total_mensal.parquet").exists()


def test_unknown_layout_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Acessos_Banda_Larga_Fixa_2027.csv", f"{BOM}Ano;Mês;Coluna Nova\n")

    with (
        zipfile.ZipFile(path) as archive,
        pytest.raises(anatel.LayoutError, match=r"Fixa_2027\.csv"),
    ):
        anatel.check_layouts(archive)


def test_archive_without_long_csvs_fails(tmp_path: Path) -> None:
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("outro.csv", "a;b\n")

    with zipfile.ZipFile(path) as archive, pytest.raises(anatel.LayoutError):
        anatel.check_layouts(archive)
