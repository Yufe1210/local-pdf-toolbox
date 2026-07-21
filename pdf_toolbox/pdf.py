"""Shared validation helpers for PDF features."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Sequence

from pypdf import PasswordType, PdfReader

from pdf_toolbox.errors import PDFMergeError


@dataclass(frozen=True, slots=True)
class PDFInfo:
    """Basic information collected while validating a PDF."""

    name: str
    page_count: int


def display_name(file: BinaryIO, index: int) -> str:
    """Return a safe, short name for an input stream."""

    raw_name = getattr(file, "name", None)
    if raw_name:
        return Path(str(raw_name)).name
    return f"第 {index + 1} 個檔案"


def rewind(file: BinaryIO) -> None:
    """Seek an input stream back to the beginning."""

    try:
        file.seek(0)
    except (AttributeError, OSError) as exc:
        raise PDFMergeError("檔案無法重新讀取，請重新選擇檔案。") from exc


def unlock_pdf_with_empty_password(reader: PdfReader, *, name: str) -> None:
    """Allow encryption with an empty user password and reject real passwords."""

    if not reader.is_encrypted:
        return
    try:
        password_type = reader.decrypt("")
    except Exception as exc:
        raise PDFMergeError(
            f"無法解鎖「{name}」，檔案可能需要密碼或使用不支援的加密方式。"
        ) from exc
    if password_type == PasswordType.NOT_DECRYPTED:
        raise PDFMergeError(f"「{name}」需要密碼才能開啟，目前不支援密碼輸入。")


def inspect_pdf(file: BinaryIO, *, index: int = 0) -> PDFInfo:
    """Validate one PDF and return its display name and page count."""

    name = display_name(file, index)
    try:
        rewind(file)
        header = file.read(1024)
        rewind(file)
        if not header or b"%PDF-" not in header:
            raise PDFMergeError(f"「{name}」不是有效的 PDF 檔案。")

        reader = PdfReader(file, strict=False)
        unlock_pdf_with_empty_password(reader, name=name)

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


def inspect_pdfs(files: Sequence[BinaryIO], *, minimum: int = 1) -> list[PDFInfo]:
    """Validate every PDF before a feature starts producing output."""

    if len(files) < minimum:
        if minimum == 1:
            raise PDFMergeError("請選擇至少 1 個 PDF 檔案。")
        raise PDFMergeError(f"請至少選擇 {minimum} 個 PDF 檔案。")
    return [inspect_pdf(file, index=index) for index, file in enumerate(files)]
