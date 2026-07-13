"""Toolbox home page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from pdf_toolbox import __version__


def render_home(merge_page: Any) -> None:
    """Render the simple tool selection home page."""

    st.title("本機 PDF 工具箱")
    st.caption("簡單、離線、文件留在你的電腦上。")

    st.subheader("選擇工具")
    with st.container(border=True):
        st.markdown("### 合併 PDF")
        st.write("依照指定順序，將多份 PDF 合併成一份文件。")
        if st.button("開啟合併工具", type="primary", use_container_width=True):
            st.switch_page(merge_page)

    with st.container(border=True):
        st.markdown("### 拆分 PDF")
        st.write("規劃於下一版本提供。")
        st.button("尚未開放", disabled=True, use_container_width=True)

    st.info("所有 PDF 都只在本機處理，不會上傳到外部服務。")
    st.caption(f"版本 {__version__}")

