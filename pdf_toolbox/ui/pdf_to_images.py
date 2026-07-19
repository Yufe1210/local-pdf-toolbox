"""Streamlit page for converting complete PDF pages to images."""

from __future__ import annotations

from typing import Any, Sequence

import streamlit as st

from pdf_toolbox.errors import PDFToImagesError
from pdf_toolbox.features.pdf_to_images import convert_pdfs_to_images
from pdf_toolbox.filenames import sanitize_zip_filename, unique_pdf_stems
from pdf_toolbox.ui.pdf_grid import PDFGridEvent, render_pdf_grid
from pdf_toolbox.ui.pdf_items import (
    build_pdf_item,
    named_stream,
    validate_upload_capacity,
)


MAX_PDF_FILES = 50
MAX_TOTAL_BYTES = 500 * 1024 * 1024
SUBFOLDER_OPTION = "每份 PDF 建立子資料夾（建議）"
FLAT_OPTION = "全部圖片放在 ZIP 根目錄"


def _default_zip_name(items: Sequence[dict[str, Any]]) -> str:
    if len(items) == 1:
        stem = unique_pdf_stems([str(items[0]["name"])])[0]
        return f"{stem}-images.zip"
    return "pdf-images.zip"


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "image_pdf_items": [],
        "image_uploader_version": 0,
        "image_upload_error": None,
        "image_result": None,
        "image_zip_name": "pdf-images.zip",
        "image_auto_zip_name": "pdf-images.zip",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_result() -> None:
    st.session_state.image_result = None


def _refresh_auto_zip_name() -> None:
    old_auto = st.session_state.image_auto_zip_name
    new_auto = _default_zip_name(st.session_state.image_pdf_items)
    if st.session_state.image_zip_name == old_auto:
        st.session_state.image_zip_name = new_auto
    st.session_state.image_auto_zip_name = new_auto


def _add_uploads(uploaded_files: Sequence[Any]) -> None:
    pending = [(uploaded.getvalue(), uploaded.name) for uploaded in uploaded_files]
    error = validate_upload_capacity(
        st.session_state.image_pdf_items,
        [data for data, _ in pending],
        max_files=MAX_PDF_FILES,
        max_total_bytes=MAX_TOTAL_BYTES,
    )
    if error:
        st.session_state.image_upload_error = error
        return

    st.session_state.image_upload_error = None
    for data, name in pending:
        st.session_state.image_pdf_items.append(build_pdf_item(data, name))
    _clear_result()
    _refresh_auto_zip_name()


def _apply_grid_event(event: PDFGridEvent) -> None:
    items = st.session_state.image_pdf_items
    if event.action == "reorder":
        by_id = {str(item["id"]): item for item in items}
        st.session_state.image_pdf_items = [
            by_id[item_id] for item_id in event.ordered_ids
        ]
    elif event.action == "remove" and event.item_id is not None:
        st.session_state.image_pdf_items = [
            item for item in items if str(item["id"]) != event.item_id
        ]
    st.session_state.image_upload_error = None
    _clear_result()
    _refresh_auto_zip_name()


def _clear_all() -> None:
    st.session_state.image_pdf_items = []
    st.session_state.image_uploader_version += 1
    st.session_state.image_upload_error = None
    _clear_result()
    _refresh_auto_zip_name()


def _render_pdf_cards(items: list[dict[str, Any]]) -> None:
    st.subheader("轉換清單")
    st.caption(
        "直接拖曳卡片調整順序；此順序會決定 ZIP 內容順序及重複檔名的編號。"
    )
    event = render_pdf_grid(items, key="pdf_to_images_card_grid")
    if event:
        _apply_grid_event(event)
        st.rerun()

    total_size = sum(len(item["data"]) for item in items) / 1024 / 1024
    total_pages = sum(int(item["page_count"] or 0) for item in items)
    st.caption(
        f"已加入 {len(items)} / {MAX_PDF_FILES} 份，共 {total_pages} 頁、"
        f"{total_size:.1f} / 500 MB。"
    )
    st.button("清除全部", on_click=_clear_all, key="clear_image_pdfs")


def render_pdf_to_images_page() -> None:
    """Render the complete multi-PDF to image workflow."""

    _init_state()

    st.title("PDF 轉圖片")
    st.caption("將每一頁完整轉成一張圖片，最後下載單一 ZIP；所有處理都在本機完成。")

    uploader_key = (
        f"image_pdf_uploader_{st.session_state.image_uploader_version}"
    )
    uploads = st.file_uploader(
        "加入一份或多份 PDF",
        type=["pdf"],
        accept_multiple_files=True,
        key=uploader_key,
    )
    if uploads:
        _add_uploads(uploads)
        st.session_state.image_uploader_version += 1
        st.rerun()

    if st.session_state.image_upload_error:
        st.error(st.session_state.image_upload_error, icon="⚠️")

    items = st.session_state.image_pdf_items
    if items:
        _render_pdf_cards(items)

    st.subheader("輸出設定")
    first_column, second_column = st.columns(2)
    with first_column:
        image_format_label = st.selectbox(
            "圖片格式",
            options=["PNG", "JPEG"],
            on_change=_clear_result,
        )
    with second_column:
        dpi = st.selectbox(
            "解析度",
            options=[150, 200, 300],
            index=1,
            format_func=lambda value: f"{value} DPI",
            on_change=_clear_result,
        )

    jpeg_quality = 90
    if image_format_label == "JPEG":
        jpeg_quality = st.slider(
            "JPEG 品質",
            min_value=60,
            max_value=100,
            value=90,
            on_change=_clear_result,
            help="品質越高，文字與細節通常越清楚，但 ZIP 會更大。",
        )

    structure = st.radio(
        "ZIP 檔案結構",
        options=[SUBFOLDER_OPTION, FLAT_OPTION],
        on_change=_clear_result,
    )
    st.text_input("ZIP 檔名", key="image_zip_name")

    has_invalid_file = any(item["error"] for item in items)
    can_convert = len(items) >= 1 and not has_invalid_file
    if st.button(
        "轉換並建立 ZIP",
        type="primary",
        disabled=not can_convert,
        use_container_width=True,
    ):
        streams = [named_stream(item["data"], item["name"]) for item in items]
        progress_bar = st.progress(0.0, text="正在準備轉換...")

        def update_progress(
            completed: int,
            total: int,
            source_name: str,
            page_number: int,
        ) -> None:
            progress_bar.progress(
                completed / total,
                text=f"正在轉換「{source_name}」第 {page_number} 頁（{completed}/{total}）",
            )

        try:
            result = convert_pdfs_to_images(
                streams,
                image_format="png" if image_format_label == "PNG" else "jpg",
                dpi=int(dpi),
                jpeg_quality=jpeg_quality,
                use_subfolders=structure == SUBFOLDER_OPTION,
                progress=update_progress,
            )
            try:
                st.session_state.image_result = {
                    "data": result.archive.getvalue(),
                    "image_count": result.image_count,
                    "pdf_count": result.pdf_count,
                }
            finally:
                result.archive.close()
            progress_bar.progress(1.0, text="轉換完成。")
        except PDFToImagesError as exc:
            st.session_state.image_result = None
            progress_bar.empty()
            st.error(str(exc), icon="⚠️")
        finally:
            for stream in streams:
                stream.close()

    if not items:
        st.info("請至少加入 1 個有效的 PDF 檔案。")
    elif has_invalid_file:
        st.warning("請移除無法讀取或預覽的檔案後再轉換。")

    if st.session_state.image_result:
        result = st.session_state.image_result
        filename = sanitize_zip_filename(st.session_state.image_zip_name)
        st.success(
            f"轉換完成：{result['pdf_count']} 份 PDF，共 "
            f"{result['image_count']} 張圖片。"
        )
        st.download_button(
            "下載圖片 ZIP",
            data=result["data"],
            file_name=filename,
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
