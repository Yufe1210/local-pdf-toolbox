"""In-memory PDF merge feature."""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, Sequence

from pypdf import PdfReader, PdfWriter

from pdf_toolbox.errors import PDFMergeError
from pdf_toolbox.filenames import sanitize_pdf_filename
from pdf_toolbox.pdf import display_name, inspect_pdfs, rewind


def merge_pdfs(files: Sequence[BinaryIO]) -> BytesIO:
    """Merge PDFs in sequence and return a ready-to-read memory stream."""

    inspect_pdfs(files, minimum=2)
    writer = PdfWriter()
    output = BytesIO()
    try:
        for index, file in enumerate(files):
            name = display_name(file, index)
            try:
                rewind(file)
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
    """Return a safe merge download filename."""

    return sanitize_pdf_filename(value, fallback="merged")

