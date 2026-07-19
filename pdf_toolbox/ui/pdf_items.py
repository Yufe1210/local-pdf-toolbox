"""Shared in-memory PDF upload item helpers."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Sequence
from uuid import uuid4

from pdf_toolbox.errors import PDFMergeError, PDFPreviewError
from pdf_toolbox.pdf import inspect_pdf
from pdf_toolbox.preview import DEFAULT_THUMBNAIL_WIDTH, render_first_page_thumbnail


def named_stream(data: bytes, name: str) -> BytesIO:
    """Return a named in-memory stream for validation and feature calls."""

    stream = BytesIO(data)
    stream.name = name  # type: ignore[attr-defined]
    return stream


def validate_upload_capacity(
    existing_items: Sequence[dict[str, Any]],
    new_files: Sequence[bytes],
    *,
    max_files: int,
    max_total_bytes: int,
) -> str | None:
    """Return a user-facing capacity error or None."""

    total_files = len(existing_items) + len(new_files)
    if total_files > max_files:
        return f"一次最多加入 {max_files} 份 PDF；目前這批加入後會有 {total_files} 份。"

    existing_bytes = sum(len(item["data"]) for item in existing_items)
    total_bytes = existing_bytes + sum(len(data) for data in new_files)
    if total_bytes > max_total_bytes:
        limit_mb = max_total_bytes // 1024 // 1024
        return f"PDF 總容量不可超過 {limit_mb} MB，請移除部分檔案後再試。"
    return None


def build_pdf_item(data: bytes, name: str) -> dict[str, Any]:
    """Validate a PDF and build the card state used by toolbox pages."""

    page_count: int | None = None
    validation_error: str | None = None
    thumbnail: bytes | None = None
    try:
        stream = named_stream(data, name)
        try:
            page_count = inspect_pdf(stream).page_count
        finally:
            stream.close()
        thumbnail = render_first_page_thumbnail(
            data,
            name,
            width=DEFAULT_THUMBNAIL_WIDTH,
        )
    except (PDFMergeError, PDFPreviewError) as exc:
        validation_error = str(exc)

    return {
        "id": uuid4().hex,
        "name": name,
        "data": data,
        "page_count": page_count,
        "thumbnail": thumbnail,
        "error": validation_error,
    }
