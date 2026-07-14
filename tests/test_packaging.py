import json
import re
import tomllib
from pathlib import Path

from pdf_toolbox import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_version_is_consistent_across_release_files() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version_info = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    major, minor, patch = (int(value) for value in __version__.split("."))

    assert project["project"]["version"] == __version__
    assert f"filevers=({major}, {minor}, {patch}, 0)" in version_info
    assert f"prodvers=({major}, {minor}, {patch}, 0)" in version_info
    assert f"StringStruct('FileVersion', '{__version__}')" in version_info
    assert f"StringStruct('ProductVersion', '{__version__}')" in version_info


def test_installer_is_single_file_offline_and_keeps_fixed_app_id() -> None:
    installer = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    normalized = installer.lower()

    assert "AppId={{18D34507-C3D3-4532-9F04-B88CC2D59EC8}" in installer
    assert "PrivilegesRequired=lowest" in installer
    assert "recursesubdirs" in normalized
    assert "createallsubdirs" in normalized
    assert not re.search(r"flags\s*:[^\r\n]*(?:external|download)", normalized)
    assert "filesandordirs" in normalized


def test_release_uses_github_manual_update_feed() -> None:
    config = json.loads((ROOT / "update-config.json").read_text(encoding="utf-8"))
    feed = json.loads((ROOT / "updates" / "update.json").read_text(encoding="utf-8"))
    spec = (ROOT / "packaging" / "pdf_toolbox.spec").read_text(encoding="utf-8")

    assert config == {
        "update_feed_url": (
            "https://raw.githubusercontent.com/Yufe1210/"
            "local-pdf-toolbox/main/updates/update.json"
        )
    }
    assert feed["version"] == __version__
    assert feed["release_url"] == (
        "https://github.com/Yufe1210/local-pdf-toolbox/releases/latest"
    )
    assert "download_url" not in feed
    assert 'os.environ.get("PDF_TOOLBOX_CONSOLE", "0") == "1"' in spec
    assert "COLLECT(" in spec


def test_unsigned_release_build_is_explicitly_supported() -> None:
    build_script = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8-sig")

    assert "正在建立未簽章公開測試版" in build_script
    assert "正式建置必須提供 CertificateThumbprint" not in build_script
