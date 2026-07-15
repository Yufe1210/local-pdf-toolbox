"""Fast, non-interactive checks for an installed application bundle."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter


def _representative_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=400)
    output = BytesIO()
    try:
        writer.write(output)
        return output.getvalue()
    finally:
        writer.close()
        output.close()


def run_self_test() -> tuple[str, ...]:
    """Exercise the imports and in-memory PDF path needed by the installed app."""

    from pdf_toolbox.features.merge import merge_pdfs
    from pdf_toolbox.pdf import inspect_pdf
    from pdf_toolbox.preview import render_first_page_thumbnail
    from pdf_toolbox.ui.home import render_home
    from pdf_toolbox.ui.merge import render_merge_page
    from streamlit_dnd import dnd

    if not all(callable(value) for value in (render_home, render_merge_page, dnd)):
        raise RuntimeError("介面模組無法載入。")

    pdf_data = _representative_pdf()
    source = BytesIO(pdf_data)
    source.name = "自我檢查.pdf"  # type: ignore[attr-defined]
    try:
        info = inspect_pdf(source)
        if info.page_count != 1:
            raise RuntimeError("代表性 PDF 頁數不符。")
    finally:
        source.close()

    thumbnail = render_first_page_thumbnail(pdf_data, "自我檢查.pdf", width=120)
    if not thumbnail.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("第一頁縮圖不是有效 PNG。")

    first = BytesIO(pdf_data)
    second = BytesIO(pdf_data)
    first.name = "第一.pdf"  # type: ignore[attr-defined]
    second.name = "第二.pdf"  # type: ignore[attr-defined]
    try:
        merged = merge_pdfs([first, second])
        try:
            if len(PdfReader(merged).pages) != 2:
                raise RuntimeError("合併結果頁數不符。")
        finally:
            merged.close()
    finally:
        first.close()
        second.close()

    return (
        "介面模組",
        "PDF 驗證",
        "PDFium 第一頁預覽",
        "PDF 合併",
    )
