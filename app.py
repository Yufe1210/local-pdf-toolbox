"""Streamlit user interface for the local PDF merger."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import streamlit as st

from pdf_merge import PDFMergeError, inspect_pdf, merge_pdfs, sanitize_output_filename


st.set_page_config(page_title="PDF 合併工具", page_icon="📄", layout="centered")


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "pdf_items": [],
        "seen_upload_ids": set(),
        "uploader_version": 0,
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


def _add_uploads(uploaded_files: list[Any]) -> None:
    occurrence: dict[str, int] = {}
    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        occurrence[digest] = occurrence.get(digest, 0) + 1
        fallback_id = f"{uploaded.name}:{digest}:{occurrence[digest]}"
        upload_id = str(getattr(uploaded, "file_id", fallback_id))
        if upload_id in st.session_state.seen_upload_ids:
            continue

        page_count: int | None = None
        validation_error: str | None = None
        try:
            page_count = inspect_pdf(_named_stream(data, uploaded.name)).page_count
        except PDFMergeError as exc:
            validation_error = str(exc)

        st.session_state.pdf_items.append(
            {
                "id": upload_id,
                "name": uploaded.name,
                "data": data,
                "page_count": page_count,
                "error": validation_error,
            }
        )
        st.session_state.seen_upload_ids.add(upload_id)
        _clear_result()


def _move_item(index: int, direction: int) -> None:
    target = index + direction
    items = st.session_state.pdf_items
    if 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]
        _clear_result()


def _remove_item(index: int) -> None:
    del st.session_state.pdf_items[index]
    _clear_result()


def _clear_all() -> None:
    st.session_state.pdf_items = []
    st.session_state.seen_upload_ids = set()
    st.session_state.uploader_version += 1
    _clear_result()


_init_state()

st.title("PDF 合併工具")
st.caption("檔案只在目前的程式記憶體中處理，不會上傳到外部服務或永久保存。")

uploads = st.file_uploader(
    "選擇至少 2 個 PDF",
    type=["pdf"],
    accept_multiple_files=True,
    key=f"pdf_uploader_{st.session_state.uploader_version}",
)
if uploads:
    _add_uploads(uploads)

items = st.session_state.pdf_items
if items:
    st.subheader("合併順序")
    for index, item in enumerate(list(items)):
        name_col, up_col, down_col, remove_col = st.columns([7, 1, 1, 1])
        detail = f"{item['page_count']} 頁" if item["page_count"] else "無法讀取"
        name_col.write(f"{index + 1}. {item['name']}")
        name_col.caption(detail)
        if up_col.button("↑", key=f"up_{item['id']}", disabled=index == 0, help="上移"):
            _move_item(index, -1)
            st.rerun()
        if down_col.button(
            "↓", key=f"down_{item['id']}", disabled=index == len(items) - 1, help="下移"
        ):
            _move_item(index, 1)
            st.rerun()
        if remove_col.button("✕", key=f"remove_{item['id']}", help="移除"):
            _remove_item(index)
            st.rerun()
        if item["error"]:
            st.error(item["error"], icon="⚠️")

    st.button("清除全部", on_click=_clear_all)

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
    st.warning("請移除無法讀取的檔案後再合併。")

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
