"""Application identity and local path configuration."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pdf_toolbox import __version__

APP_NAME = "本機 PDF 工具箱"
APP_ID = "LocalPDFToolbox"
APP_VERSION = __version__
LOOPBACK_HOST = "127.0.0.1"


@dataclass(frozen=True, slots=True)
class LauncherConfig:
    """Publisher-controlled launcher settings bundled with a release."""

    update_feed_url: str = ""


def resource_path(name: str) -> Path:
    """Locate a source or PyInstaller-bundled resource."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1] / name


def user_data_dir() -> Path:
    """Return the per-user directory for runtime state, never PDF content."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / APP_ID


def load_launcher_config() -> LauncherConfig:
    """Load release settings; invalid or absent configuration stays offline."""

    path = resource_path("update-config.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LauncherConfig(
            update_feed_url=str(data.get("update_feed_url", "")).strip(),
        )
    except (OSError, ValueError, TypeError):
        return LauncherConfig()
