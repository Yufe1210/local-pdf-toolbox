import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_server_command_in_packaged_mode(monkeypatch) -> None:
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", r"C:\Program Files\本機PDF工具箱.exe")

    command = launcher.server_command(54321)

    assert command == [
        r"C:\Program Files\本機PDF工具箱.exe",
        "--run-server",
        "--port",
        "54321",
    ]


def test_packaged_server_uses_private_loopback_config(monkeypatch, tmp_path: Path) -> None:
    from streamlit import config as streamlit_config
    from streamlit.web import bootstrap

    captured: dict[str, object] = {}

    def load_options(options: dict[str, object]) -> None:
        captured.update(options)

    monkeypatch.setattr(launcher, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(launcher, "resource_path", lambda name: tmp_path / name)
    monkeypatch.setattr(bootstrap, "load_config_options", load_options)
    monkeypatch.setattr(bootstrap, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(streamlit_config, "get_option", lambda key: captured.get(key.replace(".", "_")))

    assert launcher.run_streamlit_server(54321) == 0
    assert captured["global_developmentMode"] is False
    assert captured["server_address"] == "127.0.0.1"
    assert captured["server_port"] == 54321
    assert captured["server_headless"] is True
    assert captured["server_fileWatcherType"] == "none"
    assert captured["browser_gatherUsageStats"] is False
    assert "Starting server" in (tmp_path / "launcher.log").read_text(encoding="utf-8")


def test_shutdown_stops_server_and_removes_runtime_file(tmp_path: Path) -> None:
    class FakeProcess:
        terminated = False

        def poll(self):
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: int) -> None:
            assert timeout == 5

    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text("{}", encoding="utf-8")
    process = FakeProcess()
    instance = SimpleNamespace(released=False)
    instance.release = lambda: setattr(instance, "released", True)
    root = SimpleNamespace(destroyed=False)
    root.destroy = lambda: setattr(root, "destroyed", True)

    window = object.__new__(launcher.LauncherWindow)
    window.closing = False
    window.process = process
    window.runtime_path = runtime_path
    window.instance = instance
    window.root = root

    window.shutdown()

    assert window.closing
    assert process.terminated
    assert not runtime_path.exists()
    assert instance.released
    assert root.destroyed


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
