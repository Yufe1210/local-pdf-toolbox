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


def test_default_build_stays_offline_and_requires_signed_updates() -> None:
    config = json.loads((ROOT / "update-config.json").read_text(encoding="utf-8"))
    spec = (ROOT / "packaging" / "pdf_toolbox.spec").read_text(encoding="utf-8")

    assert config == {"update_feed_url": "", "require_signed_updates": True}
    assert 'os.environ.get("PDF_TOOLBOX_CONSOLE", "0") == "1"' in spec
    assert "COLLECT(" in spec
