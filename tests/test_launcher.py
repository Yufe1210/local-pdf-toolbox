import json
import socket
import sys
from pathlib import Path

import launcher
from pdf_toolbox.config import LOOPBACK_HOST, LauncherConfig, load_launcher_config


def test_find_available_port_is_loopback_bindable() -> None:
    port = launcher.find_available_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK_HOST, port))


def test_server_command_in_source_mode() -> None:
    command = launcher.server_command(54321)

    assert command[0] == sys.executable
    assert Path(command[1]).name == "launcher.py"
    assert command[-3:] == ["--run-server", "--port", "54321"]


def test_launcher_config_defaults_offline(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr("pdf_toolbox.config.resource_path", lambda name: missing)

    assert load_launcher_config() == LauncherConfig()


def test_launcher_config_reads_release_settings(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "update-config.json"
    config_path.write_text(
        json.dumps(
            {
                "update_feed_url": "https://updates.example.test/feed.json",
                "require_signed_updates": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("pdf_toolbox.config.resource_path", lambda name: config_path)

    assert load_launcher_config() == LauncherConfig(
        update_feed_url="https://updates.example.test/feed.json",
        require_signed_updates=False,
    )
