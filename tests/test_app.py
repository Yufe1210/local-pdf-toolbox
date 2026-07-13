from io import BytesIO

from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest


MERGE_PAGE_SCRIPT = """
from pdf_toolbox.ui.merge import render_merge_page
render_merge_page()
"""


def make_pdf(width: float, height: float) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    return stream.getvalue()


def merge_page_with_items(items: list[dict[str, object]]) -> AppTest:
    app = AppTest.from_string(MERGE_PAGE_SCRIPT)
    app.session_state["pdf_items"] = items
    app.session_state["seen_upload_ids"] = {str(item["id"]) for item in items}
    app.session_state["uploader_version"] = 0
    app.session_state["merged_result"] = None
    return app.run(timeout=10)


def button_with_key(app: AppTest, key: str):
    matches = [button for button in app.button if button.key == key]
    assert len(matches) == 1
    return matches[0]


def test_home_page_and_merge_navigation() -> None:
    app = AppTest.from_file("app.py").run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["本機 PDF 工具箱"]
    assert app.button[0].label == "開啟合併工具"
    assert app.button[1].label == "尚未開放"
    assert app.button[1].disabled

    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["合併 PDF"]
    assert app.button[0].label == "合併 PDF"
    assert app.button[0].disabled


def test_merge_page_reorders_and_merges_in_display_order() -> None:
    app = merge_page_with_items(
        [
            {
                "id": "first",
                "name": "文件.pdf",
                "data": make_pdf(100, 200),
                "page_count": 1,
                "error": None,
            },
            {
                "id": "second",
                "name": "文件.pdf",
                "data": make_pdf(300, 400),
                "page_count": 1,
                "error": None,
            },
        ]
    )

    button_with_key(app, "down_first").click().run(timeout=10)

    assert [item.value for item in app.markdown] == ["1. 文件.pdf", "2. 文件.pdf"]
    assert [item["id"] for item in app.session_state["pdf_items"]] == ["second", "first"]

    app.text_input[0].set_value("合併結果")
    merge_buttons = [button for button in app.button if button.label == "合併 PDF"]
    assert len(merge_buttons) == 1
    merge_buttons[0].click().run(timeout=10)

    result = app.session_state["merged_result"]
    reader = PdfReader(BytesIO(result["data"]))
    assert [(float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages] == [
        (300.0, 400.0),
        (100.0, 200.0),
    ]
    assert [message.value for message in app.success] == ["合併完成，共 2 頁。"]
    assert len(app.download_button) == 1
    assert app.download_button[0].label == "下載合併後的 PDF"


def test_merge_page_remove_and_clear_all() -> None:
    app = merge_page_with_items(
        [
            {
                "id": "first",
                "name": "第一.pdf",
                "data": make_pdf(100, 200),
                "page_count": 1,
                "error": None,
            },
            {
                "id": "second",
                "name": "第二.pdf",
                "data": make_pdf(200, 300),
                "page_count": 1,
                "error": None,
            },
            {
                "id": "third",
                "name": "第三.pdf",
                "data": make_pdf(300, 400),
                "page_count": 1,
                "error": None,
            },
        ]
    )

    button_with_key(app, "remove_second").click().run(timeout=10)

    assert [item["name"] for item in app.session_state["pdf_items"]] == [
        "第一.pdf",
        "第三.pdf",
    ]

    clear_buttons = [button for button in app.button if button.label == "清除全部"]
    assert len(clear_buttons) == 1
    clear_buttons[0].click().run(timeout=10)

    assert app.session_state["pdf_items"] == []
    assert app.session_state["seen_upload_ids"] == set()
    assert app.session_state["uploader_version"] == 1
    merge_buttons = [button for button in app.button if button.label == "合併 PDF"]
    assert len(merge_buttons) == 1
    assert merge_buttons[0].disabled
