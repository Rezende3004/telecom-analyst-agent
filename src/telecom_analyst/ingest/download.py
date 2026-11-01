"""Download idempotente, com checksum e manifesto por diretório."""

import hashlib
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
ATTEMPTS = 3
CHUNK_SIZE = 1024 * 1024


class FileRecord(BaseModel):
    url: str
    sha256: str
    size_bytes: int
    etag: str | None = None
    last_modified: str | None = None
    downloaded_at: datetime


class Manifest(BaseModel):
    reference_period: str | None = None
    files: dict[str, FileRecord] = Field(default_factory=dict)

    @classmethod
    def load(cls, directory: Path) -> "Manifest":
        path = directory / MANIFEST_NAME
        return cls.model_validate_json(path.read_text()) if path.exists() else cls()

    def save(self, directory: Path) -> None:
        temporary = directory / f"{MANIFEST_NAME}.part"
        temporary.write_text(self.model_dump_json(indent=2))
        temporary.replace(directory / MANIFEST_NAME)


def _is_unchanged(client: httpx.Client, url: str, path: Path, known: FileRecord) -> bool:
    """Compara o arquivo local com o servidor sem baixar o conteúdo."""
    if not path.exists() or path.stat().st_size != known.size_bytes or known.etag is None:
        return False
    response = client.head(url)
    return response.is_success and response.headers.get("etag") == known.etag


def _stream_to(client: httpx.Client, url: str, part: Path) -> FileRecord:
    digest = hashlib.sha256()
    size = 0
    with client.stream("GET", url) as response, part.open("wb") as output:
        response.raise_for_status()
        for chunk in response.iter_bytes(CHUNK_SIZE):
            digest.update(chunk)
            output.write(chunk)
            size += len(chunk)

    # Com gzip, content-length mede o corpo comprimido e não pode ser comparado.
    expected = response.headers.get("content-length")
    if (
        expected is not None
        and "content-encoding" not in response.headers
        and int(expected) != size
    ):
        raise httpx.ReadError(f"{url}: esperava {expected} bytes, recebeu {size}")

    return FileRecord(
        url=url,
        sha256=digest.hexdigest(),
        size_bytes=size,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        downloaded_at=datetime.now(UTC),
    )


def fetch(client: httpx.Client, url: str, directory: Path, filename: str) -> FileRecord:
    """Baixa `url` para `directory/filename`, a menos que o arquivo já esteja atualizado.

    O arquivo só substitui a versão anterior depois de completo, então uma falha no meio
    do download nunca deixa dado truncado no lugar.
    """
    directory.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load(directory)
    path = directory / filename
    known = manifest.files.get(filename)

    if known is not None and _is_unchanged(client, url, path, known):
        logger.info("%s: sem mudanças", filename)
        return known

    part = directory / f"{filename}.part"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            record = _stream_to(client, url, part)
            break
        except httpx.TransportError:
            if attempt == ATTEMPTS:
                part.unlink(missing_ok=True)
                raise
            logger.warning("%s: tentativa %d falhou", filename, attempt)
            time.sleep(2**attempt)

    if known is not None and known.sha256 == record.sha256 and path.exists():
        part.unlink()
        logger.info("%s: conteúdo idêntico ao já baixado", filename)
        return known

    part.replace(path)
    manifest.files[filename] = record
    manifest.save(directory)
    logger.info("%s: %.1f MB baixados", filename, record.size_bytes / 1e6)
    return record
