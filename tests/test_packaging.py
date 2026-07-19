import json
import re
import tomllib
from pathlib import Path

from packaging.version import Version

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
    assert "[run]" not in normalized
    assert "postinstall" not in normalized


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
    assert Version(feed["version"]) <= Version(__version__)
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


def test_installer_outputs_are_versioned_to_preserve_older_versions() -> None:
    build_script = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8-sig")
    installer = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")

    assert '"LocalPDFToolbox-Setup-v$version"' in build_script
    assert '"LocalPDFToolbox-Setup-v$version-unsigned-test"' in build_script
    assert '"$installer.sha256"' in build_script
    assert '"LocalPDFToolbox-Setup-v" + MyAppVersion + "-unsigned-test"' in installer


def test_all_toolbox_modules_are_explicit_packaging_inputs() -> None:
    spec = (ROOT / "packaging" / "pdf_toolbox.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8-sig")
    required_modules = {
        line.strip()
        for line in (ROOT / "packaging" / "required_toolbox_modules.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    source_modules = {
        ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
        if path.name == "__init__.py"
        else ".".join(path.relative_to(ROOT).with_suffix("").parts)
        for path in (ROOT / "pdf_toolbox").rglob("*.py")
    }

    assert required_modules == source_modules
    assert "required_toolbox_modules.txt" in spec
    assert "collect_submodules" not in spec
    assert "required_toolbox_modules.txt" in build_script
    assert "打包後缺少必要模組" in build_script


def test_preview_runtime_and_grid_frontend_are_packaged() -> None:
    spec = (ROOT / "packaging" / "pdf_toolbox.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8-sig")

    assert 'collect_all("pypdfium2")' in spec
    assert 'collect_all("pypdfium2_raw")' in spec
    assert 'copy_metadata("pypdfium2")' in spec
    assert "pdf_grid_frontend" in spec
    assert "打包後缺少 PDFium 原生程式庫" in build_script
    assert "打包後缺少 PDF 響應式拖曳網格前端" in build_script
    assert "第三方授權文件" in build_script


def test_release_verifier_checks_no_auto_start_and_installed_self_test() -> None:
    verifier = (ROOT / "scripts" / "verify-release.ps1").read_text(encoding="utf-8-sig")

    assert "驗證安裝完成後未自動啟動" in verifier
    assert 'ArgumentList "--self-test"' in verifier
    assert "自我檢查不應啟動本機服務" in verifier
    assert '[switch]$InteractiveGuiCheck' in verifier
    assert "Start-Process -FilePath $DesktopShortcut" in verifier
    assert 'Read-Host "全部通過後輸入 PASS' in verifier
    assert 'Read-Host "確認通過後輸入 PASS' in verifier
