import json
from pathlib import Path
from typing import Any

import pytest

from telecom_analyst.ingest import ibge

ANAPOLIS = "5201108"
NEW_MUNICIPALITY = "5101837"


def indicator_payload(values: dict[str, str | None], year: str) -> list[dict[str, Any]]:
    series = [
        {"localidade": {"id": code}, "serie": {year: value}} for code, value in values.items()
    ]
    return [{"resultados": [{"series": series}]}]


def write_raw(directory: Path) -> None:
    municipios = [
        {
            "municipio-id": int(code),
            "municipio-nome": name,
            "UF-sigla": uf,
            "UF-nome": uf_name,
            "regiao-nome": "Centro-Oeste",
        }
        for code, name, uf, uf_name in (
            (ANAPOLIS, "Anápolis", "GO", "Goiás"),
            (NEW_MUNICIPALITY, "Boa Esperança do Norte", "MT", "Mato Grosso"),
        )
    ]
    (directory / ibge.MUNICIPIOS_FILE).write_text(json.dumps(municipios))
    payloads = {
        "populacao": ({ANAPOLIS: "424647", NEW_MUNICIPALITY: "5983"}, "2026"),
        "domicilios": ({ANAPOLIS: "142329"}, "2022"),
        "pib_mil_reais": ({ANAPOLIS: "1000", NEW_MUNICIPALITY: "..."}, "2023"),
        "renda_per_capita": ({ANAPOLIS: "2000.50", NEW_MUNICIPALITY: "-"}, "2022"),
    }
    for name, (values, year) in payloads.items():
        (directory / f"{name}.json").write_text(json.dumps(indicator_payload(values, year)))


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2668.80", 2668.8), ("-", None), ("...", None), ("X", None), (None, None)],
)
def test_parse_value(value: str | None, expected: float | None) -> None:
    assert ibge.parse_value(value) == expected


def test_build_table_joins_indicators_by_municipality(tmp_path: Path) -> None:
    write_raw(tmp_path)

    table = ibge.build_table(tmp_path).sort("municipio_ibge", descending=True)

    row = table.row(0, named=True)
    assert row["municipio_ibge"] == ANAPOLIS
    assert row["populacao"] == 424647
    assert row["domicilios"] == 142329
    assert row["renda_per_capita"] == 2000.5


def test_municipality_without_census_keeps_reference_years(tmp_path: Path) -> None:
    write_raw(tmp_path)

    table = ibge.build_table(tmp_path).sort("municipio_ibge")

    row = table.row(0, named=True)
    assert row["municipio_ibge"] == NEW_MUNICIPALITY
    assert row["domicilios"] is None
    assert row["domicilios_ano"] == 2022
    assert row["pib_ano"] == 2023


def test_build_table_rejects_repeated_municipality(tmp_path: Path) -> None:
    write_raw(tmp_path)
    repeated = indicator_payload({ANAPOLIS: "1"}, "2026")
    repeated[0]["resultados"].append(repeated[0]["resultados"][0])
    (tmp_path / "populacao.json").write_text(json.dumps(repeated))

    with pytest.raises(Exception, match="join keys"):
        ibge.build_table(tmp_path)
