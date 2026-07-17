import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pdf_toolbox.updater import (
    UpdateError,
    check_for_update,
)


class UpdateHandler(BaseHTTPRequestHandler):
    version = "0.2.0"

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
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def update_server():
    UpdateHandler.version = "0.2.0"
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpdateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_check_for_update_returns_manual_release_link(update_server: str) -> None:
    update = check_for_update(
        f"{update_server}/manual-feed.json",
        current_version="0.1.0",
    )

    assert update is not None
    assert update.version == "0.2.0"
    assert update.release_url.endswith("/releases/latest")
    assert update.release_notes == ("新增拆分 PDF",)


def test_current_version_does_not_offer_update(update_server: str) -> None:
    UpdateHandler.version = "0.1.0"

    assert (
        check_for_update(
            f"{update_server}/manual-feed.json",
            current_version="0.1.0",
        )
        is None
    )


def test_rejects_insecure_remote_feed() -> None:
    with pytest.raises(UpdateError, match="HTTPS"):
        check_for_update("http://example.com/feed.json")


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
