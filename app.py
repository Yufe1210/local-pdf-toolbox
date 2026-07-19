"""Streamlit entry point for the Local PDF Toolbox."""

from __future__ import annotations

import streamlit as st

from pdf_toolbox.ui.home import render_home
from pdf_toolbox.ui.merge import render_merge_page
from pdf_toolbox.ui.pdf_to_images import render_pdf_to_images_page
from pdf_toolbox.ui.shutdown_notice import render_shutdown_monitor


st.set_page_config(page_title="本機 PDF 工具箱", page_icon="📄", layout="wide")
render_shutdown_monitor()

merge_page = st.Page(render_merge_page, title="合併 PDF", icon="🔗", url_path="merge")
pdf_to_images_page = st.Page(
    render_pdf_to_images_page,
    title="PDF 轉圖片",
    icon="🖼️",
    url_path="pdf-to-images",
)


def home_page() -> None:
    render_home(merge_page, pdf_to_images_page)


home = st.Page(home_page, title="首頁", icon="🏠", url_path="", default=True)
navigation = st.navigation([home, merge_page, pdf_to_images_page], position="top")
navigation.run()
