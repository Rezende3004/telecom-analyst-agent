"""Roda a ingestão: `python -m telecom_analyst.ingest`."""

import logging

import httpx
import polars as pl

from telecom_analyst.config import load_settings
from telecom_analyst.ingest import anatel, ibge

TIMEOUT = httpx.Timeout(60, read=300)
logger = logging.getLogger(__name__)


def check_municipalities(acessos_ibge: pl.Series, ibge_codes: pl.Series) -> None:
    unknown = set(acessos_ibge.to_list()) - set(ibge_codes.to_list())
    if unknown:
        raise ValueError(f"municípios da Anatel fora do IBGE: {sorted(unknown)[:10]}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = load_settings()

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        ibge.download(settings, client)
        anatel.download(settings, client)

    ibge.build_staging(settings)
    period = anatel.build_staging(settings)

    acessos = pl.scan_parquet(anatel.staging_dir(settings) / "acessos" / "*" / "*.parquet")
    check_municipalities(
        acessos.select("municipio_ibge").unique().collect().to_series(),
        pl.read_parquet(ibge.staging_path(settings), columns=["municipio_ibge"]).to_series(),
    )
    logger.info("ingestão concluída: dados da Anatel até %s", period)


if __name__ == "__main__":
    main()
