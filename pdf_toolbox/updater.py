"""Secure, opt-in full-installer update support."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version

from pdf_toolbox.config import APP_ID, APP_VERSION

MAX_FEED_BYTES = 256 * 1024
MAX_INSTALLER_BYTES = 750 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(RuntimeError):
    """A safe message for update check or download failures."""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Validated information for one newer release."""

    version: str
    download_url: str
    sha256: str
    release_notes: tuple[str, ...]


def _is_secure_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https" and bool(parsed.netloc):
        return True
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _read_limited(response: object, limit: int) -> bytes:
    content_length = getattr(response, "headers", {}).get("Content-Length")
    if content_length and int(content_length) > limit:
        raise UpdateError("更新資料超過允許大小。")
    data = response.read(limit + 1)  # type: ignore[attr-defined]
    if len(data) > limit:
        raise UpdateError("更新資料超過允許大小。")
    return data


def _validate_final_url(response: object, requested_url: str, message: str) -> None:
    """Reject redirects that leave the allowed HTTPS or loopback transports."""

    get_url = getattr(response, "geturl", None)
    final_url = str(get_url()) if callable(get_url) else requested_url
    if not _is_secure_url(final_url):
        raise UpdateError(message)


def check_for_update(
    feed_url: str,
    *,
    current_version: str = APP_VERSION,
    timeout: float = 4.0,
) -> UpdateInfo | None:
    """Return a validated newer release without sending user document data."""

    if not feed_url:
        return None
    if not _is_secure_url(feed_url):
        raise UpdateError("更新來源必須使用 HTTPS。")

    request = urllib.request.Request(
        feed_url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{APP_ID}/{current_version}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            _validate_final_url(response, feed_url, "更新來源重新導向到不安全位置。")
            payload = json.loads(_read_limited(response, MAX_FEED_BYTES).decode("utf-8"))
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError("目前無法取得更新資訊。") from exc

    try:
        version_text = str(payload["version"])
        remote_version = Version(version_text)
        installed_version = Version(current_version)
        download_url = str(payload["download_url"])
        sha256 = str(payload["sha256"]).lower()
        notes_value = payload.get("release_notes", [])
        if not isinstance(notes_value, list):
            raise TypeError
        notes = tuple(str(note)[:500] for note in notes_value[:20])
    except (KeyError, TypeError, InvalidVersion) as exc:
        raise UpdateError("更新資訊格式不正確。") from exc

    if remote_version <= installed_version:
        return None
    if not _is_secure_url(download_url):
        raise UpdateError("新版下載位置必須使用 HTTPS。")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise UpdateError("更新資訊缺少有效的 SHA-256。")

    return UpdateInfo(
        version=version_text,
        download_url=download_url,
        sha256=sha256,
        release_notes=notes,
    )


def sha256_file(path: Path) -> str:
    """Calculate a file hash without loading the installer into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_installer(
    update: UpdateInfo,
    *,
    destination_dir: Path | None = None,
    timeout: float = 30.0,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Download and hash-check a complete installer using an atomic rename."""

    target_dir = destination_dir or Path(tempfile.gettempdir()) / APP_ID
    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / f"{APP_ID}-{update.version}-setup.exe"
    partial_path = final_path.with_suffix(".part")
    partial_path.unlink(missing_ok=True)

    request = urllib.request.Request(
        update.download_url,
        headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"},
    )
    downloaded = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            _validate_final_url(
                response,
                update.download_url,
                "新版下載位置重新導向到不安全位置。",
            )
            header = response.headers.get("Content-Length")
            total = int(header) if header else None
            if total is not None and total > MAX_INSTALLER_BYTES:
                raise UpdateError("新版安裝程式超過允許大小。")
            with partial_path.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > MAX_INSTALLER_BYTES:
                        raise UpdateError("新版安裝程式超過允許大小。")
                    output.write(chunk)
                    if progress:
                        progress(downloaded, total)
        if sha256_file(partial_path) != update.sha256:
            raise UpdateError("新版安裝程式驗證失敗，檔案可能不完整。")
        os.replace(partial_path, final_path)
        return final_path
    except UpdateError:
        partial_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        partial_path.unlink(missing_ok=True)
        raise UpdateError("下載新版安裝程式失敗。") from exc


def cleanup_downloaded_installers(destination_dir: Path | None = None) -> None:
    """Best-effort cleanup of installers and partial downloads from earlier runs."""

    target_dir = destination_dir or Path(tempfile.gettempdir()) / APP_ID
    if not target_dir.is_dir():
        return
    for pattern in (f"{APP_ID}-*-setup.exe", f"{APP_ID}-*-setup.part"):
        for path in target_dir.glob(pattern):
            try:
                path.unlink()
            except OSError:
                pass
    try:
        target_dir.rmdir()
    except OSError:
        pass


def has_valid_authenticode_signature(path: Path) -> bool:
    """Ask Windows to verify the installer's embedded Authenticode signature."""

    if os.name != "nt":
        return False

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = [
            ("cbStruct", ctypes.c_ulong),
            ("pcwszFilePath", ctypes.c_wchar_p),
            ("hFile", ctypes.c_void_p),
            ("pgKnownSubject", ctypes.c_void_p),
        ]

    class WINTRUST_DATA(ctypes.Structure):
        _fields_ = [
            ("cbStruct", ctypes.c_ulong),
            ("pPolicyCallbackData", ctypes.c_void_p),
            ("pSIPClientData", ctypes.c_void_p),
            ("dwUIChoice", ctypes.c_ulong),
            ("fdwRevocationChecks", ctypes.c_ulong),
            ("dwUnionChoice", ctypes.c_ulong),
            ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
            ("dwStateAction", ctypes.c_ulong),
            ("hWVTStateData", ctypes.c_void_p),
            ("pwszURLReference", ctypes.c_wchar_p),
            ("dwProvFlags", ctypes.c_ulong),
            ("dwUIContext", ctypes.c_ulong),
            ("pSignatureSettings", ctypes.c_void_p),
        ]

    action = GUID(
        0x00AAC56B,
        0xCD44,
        0x11D0,
        (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
    )
    file_info = WINTRUST_FILE_INFO(
        ctypes.sizeof(WINTRUST_FILE_INFO), str(path.resolve()), None, None
    )
    trust_data = WINTRUST_DATA(
        ctypes.sizeof(WINTRUST_DATA),
        None,
        None,
        2,
        0,
        1,
        ctypes.pointer(file_info),
        0,
        None,
        None,
        0,
        0,
        None,
    )
    result = ctypes.windll.wintrust.WinVerifyTrust(  # type: ignore[attr-defined]
        None, ctypes.byref(action), ctypes.byref(trust_data)
    )
    return result == 0
