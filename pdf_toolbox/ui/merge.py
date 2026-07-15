"""Streamlit page for merging PDF files."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Sequence
from uuid import uuid4

import streamlit as st
from streamlit_dnd import DropEvent, apply_move, dnd

from pdf_toolbox.errors import PDFMergeError, PDFPreviewError
from pdf_toolbox.features.merge import merge_pdfs, sanitize_output_filename
from pdf_toolbox.pdf import inspect_pdf
from pdf_toolbox.preview import DEFAULT_THUMBNAIL_WIDTH, render_first_page_thumbnail


MAX_PDF_FILES = 50
MAX_TOTAL_BYTES = 500 * 1024 * 1024
SORTABLE_CONTAINER_KEY = "pdf_sortable_cards"


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "pdf_items": [],
        "uploader_version": 0,
        "upload_error": None,
        "merged_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _named_stream(data: bytes, name: str) -> BytesIO:
    stream = BytesIO(data)
    stream.name = name  # type: ignore[attr-defined]
    return stream


def _clear_result() -> None:
    st.session_state.merged_result = None


def _validate_upload_capacity(
    existing_items: Sequence[dict[str, Any]],
    new_files: Sequence[bytes],
) -> str | None:
    total_files = len(existing_items) + len(new_files)
    if total_files > MAX_PDF_FILES:
        return f"一次最多加入 {MAX_PDF_FILES} 份 PDF；目前這批加入後會有 {total_files} 份。"

    existing_bytes = sum(len(item["data"]) for item in existing_items)
    total_bytes = existing_bytes + sum(len(data) for data in new_files)
    if total_bytes > MAX_TOTAL_BYTES:
        return "PDF 總容量不可超過 500 MB，請移除部分檔案後再試。"
    return None


def _build_pdf_item(data: bytes, name: str) -> dict[str, Any]:
    page_count: int | None = None
    validation_error: str | None = None
    thumbnail: bytes | None = None
    try:
        stream = _named_stream(data, name)
        try:
            page_count = inspect_pdf(stream).page_count
        finally:
            stream.close()
        thumbnail = render_first_page_thumbnail(data, name, width=DEFAULT_THUMBNAIL_WIDTH)
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


def _add_uploads(uploaded_files: Sequence[Any]) -> None:
    pending = [(uploaded.getvalue(), uploaded.name) for uploaded in uploaded_files]
    error = _validate_upload_capacity(
        st.session_state.pdf_items,
        [data for data, _ in pending],
    )
    if error:
        st.session_state.upload_error = error
        return

    st.session_state.upload_error = None
    for data, name in pending:
        # Each item is fully inspected and rendered before the next PDF is opened.
        st.session_state.pdf_items.append(_build_pdf_item(data, name))
    _clear_result()


def _move_item(index: int, direction: int) -> None:
    target = index + direction
    items = st.session_state.pdf_items
    if 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]
        _clear_result()


def _apply_drop(event: DropEvent, items: list[dict[str, Any]]) -> None:
    apply_move(event, {SORTABLE_CONTAINER_KEY: items})


def _remove_item(index: int) -> None:
    del st.session_state.pdf_items[index]
    st.session_state.upload_error = None
    _clear_result()


def _clear_all() -> None:
    st.session_state.pdf_items = []
    st.session_state.uploader_version += 1
    st.session_state.upload_error = None
    _clear_result()


def _render_pdf_card(index: int, item: dict[str, Any], item_count: int) -> None:
    with st.container(key=f"pdf_card_{item['id']}", border=True):
        preview_col, detail_col, up_col, down_col, remove_col = st.columns(
            [2.2, 4.8, 0.7, 0.7, 0.7], vertical_alignment="center"
        )
        with preview_col:
            if item.get("thumbnail"):
                st.image(item["thumbnail"], width="stretch")
            else:
                st.caption("無法顯示預覽")
        with detail_col:
            st.markdown(f"**{index + 1}. {item['name']}**")
            if item["page_count"] is not None:
                st.caption(f"{item['page_count']} 頁 · {len(item['data']) / 1024 / 1024:.1f} MB")
            else:
                st.caption(f"無法讀取 · {len(item['data']) / 1024 / 1024:.1f} MB")
        with up_col:
            if st.button(
                "↑",
                key=f"up_{item['id']}",
                disabled=index == 0,
                help="上移",
                use_container_width=True,
            ):
                _move_item(index, -1)
                st.rerun()
        with down_col:
            if st.button(
                "↓",
                key=f"down_{item['id']}",
                disabled=index == item_count - 1,
                help="下移",
                use_container_width=True,
            ):
                _move_item(index, 1)
                st.rerun()
        with remove_col:
            if st.button(
                "✕",
                key=f"remove_{item['id']}",
                help="移除",
                use_container_width=True,
            ):
                _remove_item(index)
                st.rerun()
        if item["error"]:
            st.error(item["error"], icon="⚠️")


def _render_pdf_cards(items: list[dict[str, Any]]) -> None:
    st.subheader("合併順序")
    st.caption("拖曳卡片右上角的把手調整順序，或使用 ↑／↓ 按鈕。")
    with st.container(key=SORTABLE_CONTAINER_KEY):
        for index, item in enumerate(list(items)):
            _render_pdf_card(index, item, len(items))

    event = dnd(
        SORTABLE_CONTAINER_KEY,
        cross=False,
        handle=True,
        handle_corner="top-right",
        handle_icon=":material/drag_indicator:",
        indicator="ghost",
        key="pdf_card_order",
    )
    if event:
        _apply_drop(event, items)
        _clear_result()
        st.rerun()

    total_size = sum(len(item["data"]) for item in items) / 1024 / 1024
    st.caption(f"已加入 {len(items)} / {MAX_PDF_FILES} 份，共 {total_size:.1f} / 500 MB。")
    st.button("清除全部", on_click=_clear_all)


def render_merge_page() -> None:
    """Render the complete merge workflow."""

    _init_state()

    st.title("合併 PDF")
    st.caption("選擇檔案、檢查第一頁預覽、調整順序，然後下載合併結果。")

    uploader_key = f"pdf_uploader_{st.session_state.uploader_version}"
    uploads = st.file_uploader(
        "加入 PDF（至少需要 2 份）",
        type=["pdf"],
        accept_multiple_files=True,
        key=uploader_key,
    )
    if uploads:
        _add_uploads(uploads)
        st.session_state.uploader_version += 1
        st.rerun()

    if st.session_state.upload_error:
        st.error(st.session_state.upload_error, icon="⚠️")

    items = st.session_state.pdf_items
    if items:
        _render_pdf_cards(items)

    output_name = st.text_input("輸出檔名", value="merged.pdf")
    has_invalid_file = any(item["error"] for item in items)
    can_merge = len(items) >= 2 and not has_invalid_file

    if st.button("合併 PDF", type="primary", disabled=not can_merge, use_container_width=True):
        streams = [_named_stream(item["data"], item["name"]) for item in items]
        try:
            with st.spinner("正在合併..."):
                result = merge_pdfs(streams)
                st.session_state.merged_result = {
                    "data": result.getvalue(),
                    "page_count": sum(item["page_count"] for item in items),
                }
                result.close()
        except PDFMergeError as exc:
            st.session_state.merged_result = None
            st.error(str(exc), icon="⚠️")
        finally:
            for stream in streams:
                stream.close()

    if len(items) < 2:
        st.info("請至少加入 2 個有效的 PDF 檔案。")
    elif has_invalid_file:
        st.warning("請移除無法讀取或預覽的檔案後再合併。")

    if st.session_state.merged_result:
        result = st.session_state.merged_result
        filename = sanitize_output_filename(output_name)
        st.success(f"合併完成，共 {result['page_count']} 頁。")
        st.download_button(
            "下載合併後的 PDF",
            data=result["data"],
            file_name=filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
