"""Secure update checks that direct users to a manual installer download."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from packaging.version import InvalidVersion, Version

from pdf_toolbox.config import APP_ID, APP_VERSION

MAX_FEED_BYTES = 256 * 1024


class UpdateError(RuntimeError):
    """A safe message for update check or download failures."""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Validated information for one newer release."""

    version: str
    release_url: str
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
        release_url = str(payload["release_url"])
        notes_value = payload.get("release_notes", [])
        if not isinstance(notes_value, list):
            raise TypeError
        notes = tuple(str(note)[:500] for note in notes_value[:20])
    except (KeyError, TypeError, InvalidVersion) as exc:
        raise UpdateError("更新資訊格式不正確。") from exc

    if remote_version <= installed_version:
        return None
    if not _is_secure_url(release_url):
        raise UpdateError("GitHub 下載頁面必須使用 HTTPS。")

    return UpdateInfo(
        version=version_text,
        release_url=release_url,
        release_notes=notes,
    )
