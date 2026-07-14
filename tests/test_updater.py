import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from pdf_toolbox.updater import (
    UpdateError,
    check_for_update,
    cleanup_downloaded_installers,
    download_installer,
)


class UpdateHandler(BaseHTTPRequestHandler):
    installer = b"test installer payload"
    version = "0.2.0"
    corrupt_hash = False

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/manual-feed.json":
            payload = json.dumps(
                {
                    "version": self.version,
                    "release_url": "https://github.com/example/pdf-toolbox/releases/latest",
                    "release_notes": ["新增拆分 PDF"],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/feed.json":
            digest = hashlib.sha256(self.installer).hexdigest()
            if self.corrupt_hash:
                digest = "0" * 64
            payload = json.dumps(
                {
                    "version": self.version,
                    "release_url": "https://github.com/example/pdf-toolbox/releases/latest",
                    "download_url": f"http://127.0.0.1:{self.server.server_port}/setup.exe",
                    "sha256": digest,
                    "release_notes": ["新增拆分 PDF"],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/setup.exe":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.installer)))
            self.end_headers()
            self.wfile.write(self.installer)
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def update_server():
    UpdateHandler.version = "0.2.0"
    UpdateHandler.corrupt_hash = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpdateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_check_and_download_update(update_server: str, tmp_path: Path) -> None:
    update = check_for_update(f"{update_server}/feed.json", current_version="0.1.0")

    assert update is not None
    assert update.version == "0.2.0"
    assert update.release_url.endswith("/releases/latest")
    assert update.release_notes == ("新增拆分 PDF",)
    installer = download_installer(update, destination_dir=tmp_path)
    assert installer.read_bytes() == UpdateHandler.installer


def test_current_version_does_not_offer_update(update_server: str) -> None:
    UpdateHandler.version = "0.1.0"

    assert check_for_update(f"{update_server}/feed.json", current_version="0.1.0") is None


def test_manual_feed_does_not_require_installer_metadata(update_server: str) -> None:
    update = check_for_update(f"{update_server}/manual-feed.json", current_version="0.1.0")

    assert update is not None
    assert update.download_url is None
    assert update.sha256 is None
    assert update.release_url.endswith("/releases/latest")


def test_rejects_insecure_remote_feed() -> None:
    with pytest.raises(UpdateError, match="HTTPS"):
        check_for_update("http://example.com/feed.json")


def test_rejects_corrupted_download(update_server: str, tmp_path: Path) -> None:
    UpdateHandler.corrupt_hash = True
    update = check_for_update(f"{update_server}/feed.json", current_version="0.1.0")

    assert update is not None
    with pytest.raises(UpdateError, match="驗證失敗"):
        download_installer(update, destination_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_rejects_insecure_redirect(monkeypatch) -> None:
    class RedirectedResponse:
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def geturl(self) -> str:
            return "http://downloads.example.test/feed.json"

        def read(self, size: int) -> bytes:
            return b"{}"

    monkeypatch.setattr(
        "pdf_toolbox.updater.urllib.request.urlopen",
        lambda request, timeout: RedirectedResponse(),
    )

    with pytest.raises(UpdateError, match="不安全位置"):
        check_for_update("https://updates.example.test/feed.json")


def test_cleanup_downloaded_installers_preserves_unrelated_files(tmp_path: Path) -> None:
    installer = tmp_path / "LocalPDFToolbox-0.2.0-setup.exe"
    partial = tmp_path / "LocalPDFToolbox-0.3.0-setup.part"
    unrelated = tmp_path / "keep.txt"
    installer.write_bytes(b"installer")
    partial.write_bytes(b"partial")
    unrelated.write_bytes(b"keep")

    cleanup_downloaded_installers(tmp_path)

    assert not installer.exists()
    assert not partial.exists()
    assert unrelated.read_bytes() == b"keep"
