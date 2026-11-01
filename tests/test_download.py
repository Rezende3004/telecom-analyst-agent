import gzip
import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from telecom_analyst.ingest import download
from telecom_analyst.ingest.download import Manifest, fetch

URL = "https://example.test/file.zip"
Handler = Callable[[httpx.Request], httpx.Response]


class Server:
    """Servidor falso que registra os métodos chamados."""

    def __init__(self, body: bytes = b"content", etag: str | None = '"v1"') -> None:
        self.body = body
        self.etag = etag
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.method)
        headers = {"etag": self.etag} if self.etag else {}
        body = b"" if request.method == "HEAD" else self.body
        return httpx.Response(200, content=body, headers=headers)


def client_for(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_records_checksum_in_manifest(tmp_path: Path) -> None:
    record = fetch(client_for(Server()), URL, tmp_path, "file.zip")

    assert (tmp_path / "file.zip").read_bytes() == b"content"
    assert record.sha256 == hashlib.sha256(b"content").hexdigest()
    assert Manifest.load(tmp_path).files["file.zip"] == record


def test_skips_download_when_etag_is_unchanged(tmp_path: Path) -> None:
    server = Server()
    fetch(client_for(server), URL, tmp_path, "file.zip")
    server.calls.clear()

    fetch(client_for(server), URL, tmp_path, "file.zip")

    assert server.calls == ["HEAD"]


def test_downloads_again_when_etag_changes(tmp_path: Path) -> None:
    server = Server()
    fetch(client_for(server), URL, tmp_path, "file.zip")
    server.body, server.etag = b"new content", '"v2"'

    record = fetch(client_for(server), URL, tmp_path, "file.zip")

    assert (tmp_path / "file.zip").read_bytes() == b"new content"
    assert record.etag == '"v2"'


def test_identical_content_keeps_original_record(tmp_path: Path) -> None:
    server = Server(etag=None)
    first = fetch(client_for(server), URL, tmp_path, "file.zip")

    second = fetch(client_for(server), URL, tmp_path, "file.zip")

    assert second.downloaded_at == first.downloaded_at


def test_stores_gzip_responses_decoded(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        body = gzip.compress(b"[1, 2, 3]")
        return httpx.Response(200, content=body, headers={"content-encoding": "gzip"})

    fetch(client_for(handler), URL, tmp_path, "file.json")

    assert (tmp_path / "file.json").read_bytes() == b"[1, 2, 3]"


def test_truncated_download_keeps_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(download.time, "sleep", lambda _: None)
    fetch(client_for(Server()), URL, tmp_path, "file.zip")

    def truncated(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"par", headers={"content-length": "100"})

    with pytest.raises(httpx.ReadError):
        fetch(client_for(truncated), URL, tmp_path, "file.zip")

    assert (tmp_path / "file.zip").read_bytes() == b"content"
    assert not (tmp_path / "file.zip.part").exists()
