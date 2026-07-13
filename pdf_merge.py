"""Backward-compatible imports for the original merge module."""

from pdf_toolbox.errors import PDFMergeError
from pdf_toolbox.features.merge import merge_pdfs, sanitize_output_filename
from pdf_toolbox.pdf import PDFInfo, inspect_pdf, inspect_pdfs

__all__ = [
    "PDFInfo",
    "PDFMergeError",
    "inspect_pdf",
    "inspect_pdfs",
    "merge_pdfs",
    "sanitize_output_filename",
]
