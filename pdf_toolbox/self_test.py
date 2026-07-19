"""Fast, non-interactive checks for an installed application bundle."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from pypdf import PdfReader, PdfWriter

from pdf_toolbox.config import resource_path


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


def _run_streamlit_pages(pdf_data: bytes, thumbnail: bytes) -> None:
    """Execute the bundled home and merge pages without opening a browser."""

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(resource_path("app.py"))).run(timeout=15)
    if app.exception:
        raise RuntimeError(f"首頁執行失敗：{app.exception[0].message}")
    if [title.value for title in app.title] != ["本機 PDF 工具箱"]:
        raise RuntimeError("首頁標題不符。")

    app.session_state["pdf_items"] = [
        {
            "id": "self-test-first",
            "name": "自我檢查.pdf",
            "data": pdf_data,
            "page_count": 1,
            "thumbnail": thumbnail,
            "error": None,
        },
        {
            "id": "self-test-second",
            "name": "自我檢查.pdf",
            "data": pdf_data,
            "page_count": 1,
            "thumbnail": thumbnail,
            "error": None,
        },
    ]
    open_merge = next(
        (button for button in app.button if button.label == "開啟合併工具"),
        None,
    )
    if open_merge is None:
        raise RuntimeError("首頁缺少合併工具入口。")
    if not any(button.label == "開啟 PDF 轉圖片" for button in app.button):
        raise RuntimeError("首頁缺少 PDF 轉圖片入口。")

    open_merge.click().run(timeout=15)
    if app.exception:
        raise RuntimeError(f"合併介面執行失敗：{app.exception[0].message}")
    if [title.value for title in app.title] != ["合併 PDF"]:
        raise RuntimeError("合併介面標題不符。")
    if len(app.session_state["pdf_items"]) != 2:
        raise RuntimeError("合併介面未保留兩份 PDF。")
    merge_buttons = [button for button in app.button if button.label == "合併 PDF"]
    if len(merge_buttons) != 1 or merge_buttons[0].disabled:
        raise RuntimeError("合併介面未進入可合併狀態。")

    image_app = AppTest.from_string(
        "from pdf_toolbox.ui.pdf_to_images import render_pdf_to_images_page\n"
        "render_pdf_to_images_page()\n"
    )
    image_app.session_state["image_pdf_items"] = [
        {
            "id": "self-test-image",
            "name": "自我檢查.pdf",
            "data": pdf_data,
            "page_count": 1,
            "thumbnail": thumbnail,
            "error": None,
        }
    ]
    image_app.session_state["image_uploader_version"] = 0
    image_app.session_state["image_upload_error"] = None
    image_app.session_state["image_result"] = None
    image_app.session_state["image_zip_name"] = "自我檢查-images.zip"
    image_app.session_state["image_auto_zip_name"] = "自我檢查-images.zip"
    image_app.run(timeout=15)
    if image_app.exception:
        raise RuntimeError(
            f"PDF 轉圖片介面執行失敗：{image_app.exception[0].message}"
        )
    if [title.value for title in image_app.title] != ["PDF 轉圖片"]:
        raise RuntimeError("PDF 轉圖片介面標題不符。")
    convert_buttons = [
        button
        for button in image_app.button
        if button.label == "轉換並建立 ZIP"
    ]
    if len(convert_buttons) != 1 or convert_buttons[0].disabled:
        raise RuntimeError("PDF 轉圖片介面未進入可轉換狀態。")


def run_self_test() -> tuple[str, ...]:
    """Exercise the imports and in-memory PDF path needed by the installed app."""

    from pdf_toolbox.features.merge import merge_pdfs
    from pdf_toolbox.features.pdf_to_images import convert_pdfs_to_images
    from pdf_toolbox.pdf import inspect_pdf
    from pdf_toolbox.preview import render_first_page_thumbnail
    from pdf_toolbox.ui.pdf_grid import PDF_GRID_FRONTEND, render_pdf_grid

    if not callable(render_pdf_grid):
        raise RuntimeError("PDF 網格元件無法載入。")
    frontend_files = {
        path.name for path in PDF_GRID_FRONTEND.iterdir() if path.is_file()
    }
    if frontend_files != {
        "index.html",
        "main.js",
        "streamlit-protocol.js",
        "styles.css",
    }:
        raise RuntimeError("PDF 網格前端檔案不完整。")

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

    _run_streamlit_pages(pdf_data, thumbnail)

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

    image_source = BytesIO(pdf_data)
    image_source.name = "自我檢查.pdf"  # type: ignore[attr-defined]
    try:
        image_result = convert_pdfs_to_images(
            [image_source],
            image_format="png",
            dpi=150,
        )
        try:
            with ZipFile(image_result.archive) as archive:
                if archive.namelist() != [
                    "自我檢查/自我檢查-001.png"
                ]:
                    raise RuntimeError("PDF 轉圖片 ZIP 結構不符。")
                image_data = archive.read("自我檢查/自我檢查-001.png")
                if not image_data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("PDF 轉圖片結果不是有效 PNG。")
        finally:
            image_result.archive.close()
    finally:
        image_source.close()

    return (
        "首頁、合併與 PDF 轉圖片介面",
        "PDF 響應式拖曳網格",
        "PDF 驗證",
        "PDFium 第一頁預覽",
        "PDF 合併",
        "PDF 轉圖片 ZIP",
    )
