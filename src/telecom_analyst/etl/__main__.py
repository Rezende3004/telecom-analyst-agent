"""Roda o ETL: `python -m telecom_analyst.etl [cnpj|load|dictionary]`."""

import argparse
import logging
from pathlib import Path

import httpx

from telecom_analyst.config import load_settings
from telecom_analyst.etl import cnpj, data_dictionary, warehouse
from telecom_analyst.ingest import anatel, receita
from telecom_analyst.ingest.download import Manifest

MANIFEST = Path("dbt/target/manifest.json")
DICTIONARY = Path("docs/data-dictionary.md")


def latest_receita_month(root: Path) -> str:
    months = sorted(path.name for path in root.iterdir() if path.is_dir())
    if not months:
        raise FileNotFoundError(f"nenhum mês baixado em {root}")
    return months[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["cnpj", "load", "dictionary"])
    step = parser.parse_args().step
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = load_settings()

    if step == "dictionary":
        data_dictionary.write(MANIFEST, DICTIONARY)
        return

    if step == "cnpj":
        with receita.make_client() as client:
            month = receita.download(settings, client)
        cnpj.build_staging(settings, month)
        return

    month = latest_receita_month(settings.data_dir / "raw" / "receita")
    period = Manifest.load(anatel.raw_dir(settings)).reference_period
    if period is None:
        raise ValueError("rode make ingest antes de carregar o warehouse")
    warehouse.load(settings, month, period)


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as error:
        raise SystemExit(f"falha ao acessar a fonte: {error}") from error
