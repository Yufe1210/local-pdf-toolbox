from io import BytesIO

from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest
from streamlit_dnd import DropEvent

from pdf_toolbox.ui import merge as merge_ui
from pdf_toolbox.ui.shutdown_notice import SHUTDOWN_MONITOR_HTML


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
    app.session_state["uploader_version"] = 0
    app.session_state["upload_error"] = None
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


def test_browser_shutdown_monitor_waits_for_health_then_shows_closed_state() -> None:
    assert "/_stcore/health" in SHUTDOWN_MONITOR_HTML
    assert "hasBeenHealthy" in SHUTDOWN_MONITOR_HTML
    assert "consecutiveFailures >= 3" in SHUTDOWN_MONITOR_HTML
    assert "本機 PDF 工具箱已關閉" in SHUTDOWN_MONITOR_HTML
    assert "window.close" not in SHUTDOWN_MONITOR_HTML


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

    assert [item.value for item in app.markdown] == ["**1. 文件.pdf**", "**2. 文件.pdf**"]
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
    assert app.session_state["uploader_version"] == 1
    merge_buttons = [button for button in app.button if button.label == "合併 PDF"]
    assert len(merge_buttons) == 1
    assert merge_buttons[0].disabled


def test_capacity_accepts_the_limit_and_rejects_a_batch_over_it(monkeypatch) -> None:
    monkeypatch.setattr(merge_ui, "MAX_PDF_FILES", 2)
    monkeypatch.setattr(merge_ui, "MAX_TOTAL_BYTES", 10)
    existing = [{"data": b"1234"}]

    assert merge_ui._validate_upload_capacity(existing, [b"123456"]) is None
    assert "最多加入 2 份" in merge_ui._validate_upload_capacity(existing, [b"1", b"2"])
    assert "總容量" in merge_ui._validate_upload_capacity(existing, [b"1234567"])


def test_pdf_items_support_duplicate_chinese_names_and_have_thumbnails() -> None:
    data = make_pdf(100, 200)

    first = merge_ui._build_pdf_item(data, "中文文件.pdf")
    second = merge_ui._build_pdf_item(data, "中文文件.pdf")

    assert first["id"] != second["id"]
    assert first["name"] == second["name"] == "中文文件.pdf"
    assert first["thumbnail"].startswith(b"\x89PNG")
    assert second["thumbnail"].startswith(b"\x89PNG")


def test_invalid_pdf_item_has_no_thumbnail_and_disables_partial_work() -> None:
    item = merge_ui._build_pdf_item(b"not a pdf", "損壞.pdf")

    assert item["page_count"] is None
    assert item["thumbnail"] is None
    assert "不是有效的 PDF" in item["error"]


def test_drag_event_reorders_the_same_list_used_for_merging() -> None:
    items = [{"id": "first"}, {"id": "second"}, {"id": "third"}]
    event = DropEvent(
        from_container=merge_ui.SORTABLE_CONTAINER_KEY,
        to_container=merge_ui.SORTABLE_CONTAINER_KEY,
        item_key="pdf_card_first",
        from_index=0,
        to_index=3,
    )

    merge_ui._apply_drop(event, items)

    assert [item["id"] for item in items] == ["second", "third", "first"]
