"""Validation and in-memory PDF merging utilities."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Sequence

from pypdf import PdfReader, PdfWriter


class PDFMergeError(ValueError):
    """A user-facing error raised when one or more PDFs cannot be merged."""


@dataclass(frozen=True, slots=True)
class PDFInfo:
    """Basic information collected while validating a PDF."""

    name: str
    page_count: int


def _display_name(file: BinaryIO, index: int) -> str:
    raw_name = getattr(file, "name", None)
    if raw_name:
        return Path(str(raw_name)).name
    return f"第 {index + 1} 個檔案"


def _rewind(file: BinaryIO) -> None:
    try:
        file.seek(0)
    except (AttributeError, OSError) as exc:
        raise PDFMergeError("檔案無法重新讀取，請重新選擇檔案。") from exc


def inspect_pdf(file: BinaryIO, *, index: int = 0) -> PDFInfo:
    """Validate one PDF and return its display name and page count."""

    name = _display_name(file, index)
    try:
        _rewind(file)
        header = file.read(1024)
        _rewind(file)
        if not header or b"%PDF-" not in header:
            raise PDFMergeError(f"「{name}」不是有效的 PDF 檔案。")

        reader = PdfReader(file, strict=False)
        if reader.is_encrypted:
            raise PDFMergeError(f"「{name}」受到密碼保護，第一版不支援合併。")

        page_count = len(reader.pages)
        if page_count == 0:
            raise PDFMergeError(f"「{name}」沒有任何頁面。")
        return PDFInfo(name=name, page_count=page_count)
    except PDFMergeError:
        raise
    except Exception as exc:
        raise PDFMergeError(f"無法讀取「{name}」，檔案可能已損壞。") from exc
    finally:
        try:
            file.seek(0)
        except (AttributeError, OSError):
            pass


def inspect_pdfs(files: Sequence[BinaryIO]) -> list[PDFInfo]:
    """Validate every input before any output is produced."""

    if len(files) < 2:
        raise PDFMergeError("請至少選擇 2 個 PDF 檔案。")
    return [inspect_pdf(file, index=index) for index, file in enumerate(files)]


def merge_pdfs(files: Sequence[BinaryIO]) -> BytesIO:
    """Merge PDFs in sequence and return a ready-to-read in-memory stream."""

    inspect_pdfs(files)
    writer = PdfWriter()
    output = BytesIO()
    try:
        for index, file in enumerate(files):
            name = _display_name(file, index)
            try:
                _rewind(file)
                reader = PdfReader(file, strict=False)
                writer.append(reader, import_outline=False)
            except Exception as exc:
                raise PDFMergeError(f"合併「{name}」時發生錯誤。") from exc
        writer.write(output)
        output.seek(0)
        return output
    except Exception:
        output.close()
        raise
    finally:
        writer.close()
        for file in files:
            try:
                file.seek(0)
            except (AttributeError, OSError):
                pass


def sanitize_output_filename(value: str) -> str:
    """Return a safe download filename ending in .pdf."""

    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid or ord(char) < 32 else char for char in value)
    cleaned = cleaned.strip().rstrip(". ")
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4].rstrip(". ")
    if not cleaned:
        cleaned = "merged"
    return f"{cleaned}.pdf"
