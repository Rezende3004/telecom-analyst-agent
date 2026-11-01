"""Base pública do CNPJ, publicada em um compartilhamento Nextcloud da Receita Federal."""

import logging
import re
from pathlib import Path

import httpx

from telecom_analyst.config import Settings
from telecom_analyst.ingest.download import Manifest, fetch

logger = logging.getLogger(__name__)

SHARE_TOKEN = "gn672Ad4CF8N6TK"  # noqa: S105 - token público do compartilhamento
WEBDAV_URL = "https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ"
PARTITIONED_TABLES = ("Empresas", "Estabelecimentos", "Socios")
LOOKUP_TABLES = ("Cnaes", "Motivos", "Municipios", "Naturezas", "Qualificacoes")
REQUIRED_FILES = frozenset(
    {f"{table}{part}.zip" for table in PARTITIONED_TABLES for part in range(10)}
    | {f"{table}.zip" for table in LOOKUP_TABLES}
)
MONTH = re.compile(r"/CNPJ/(\d{4}-\d{2})/</d:href>")


class IncompleteReleaseError(ValueError):
    """O mês publicado não tem todos os arquivos esperados."""


def raw_dir(settings: Settings, month: str) -> Path:
    return settings.data_dir / "raw" / "receita" / month


def make_client() -> httpx.Client:
    return httpx.Client(
        auth=(SHARE_TOKEN, ""), timeout=httpx.Timeout(60, read=300), follow_redirects=True
    )


def _list(client: httpx.Client, url: str) -> str:
    response = client.request("PROPFIND", url, headers={"Depth": "1"})
    response.raise_for_status()
    return response.text


def latest_month(client: httpx.Client) -> str:
    months = MONTH.findall(_list(client, f"{WEBDAV_URL}/"))
    if not months:
        raise IncompleteReleaseError("nenhum mês encontrado no compartilhamento")
    return str(max(months))


def check_release(listing: str, month: str) -> None:
    published = set(re.findall(rf"/{month}/([^/<]+\.zip)</d:href>", listing))
    missing = REQUIRED_FILES - published
    if missing:
        raise IncompleteReleaseError(f"{month}: faltam {sorted(missing)}")


def download(settings: Settings, client: httpx.Client) -> str:
    """Baixa o mês mais recente publicado e devolve esse mês (AAAA-MM)."""
    month = latest_month(client)
    check_release(_list(client, f"{WEBDAV_URL}/{month}/"), month)

    directory = raw_dir(settings, month)
    for name in sorted(REQUIRED_FILES):
        fetch(client, f"{WEBDAV_URL}/{month}/{name}", directory, name)

    manifest = Manifest.load(directory)
    manifest.reference_period = month
    manifest.save(directory)
    return month
