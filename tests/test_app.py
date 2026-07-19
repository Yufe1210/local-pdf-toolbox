from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest

from pdf_toolbox.ui import merge as merge_ui
from pdf_toolbox.ui import pdf_to_images as images_ui
from pdf_toolbox.ui.pdf_grid import PDFGridEvent
from pdf_toolbox.ui.shutdown_notice import SHUTDOWN_MONITOR_HTML


MERGE_PAGE_SCRIPT = """
from pdf_toolbox.ui.merge import render_merge_page
render_merge_page()
"""

IMAGES_PAGE_SCRIPT = """
from pdf_toolbox.ui.pdf_to_images import render_pdf_to_images_page
render_pdf_to_images_page()
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


def test_home_page_and_merge_navigation() -> None:
    app = AppTest.from_file("app.py").run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["本機 PDF 工具箱"]
    assert app.button[0].label == "開啟合併工具"
    assert app.button[1].label == "開啟 PDF 轉圖片"
    assert not app.button[1].disabled

    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["合併 PDF"]
    merge_buttons = [button for button in app.button if button.label == "合併 PDF"]
    assert len(merge_buttons) == 1
    assert merge_buttons[0].disabled


def image_page_with_items(items: list[dict[str, object]]) -> AppTest:
    app = AppTest.from_string(IMAGES_PAGE_SCRIPT)
    app.session_state["image_pdf_items"] = items
    app.session_state["image_uploader_version"] = 0
    app.session_state["image_upload_error"] = None
    app.session_state["image_result"] = None
    app.session_state["image_zip_name"] = "pdf-images.zip"
    app.session_state["image_auto_zip_name"] = "pdf-images.zip"
    return app.run(timeout=10)


def test_home_navigates_to_pdf_to_images_page() -> None:
    app = AppTest.from_file("app.py").run(timeout=10)

    app.button[1].click().run(timeout=10)

    assert not app.exception
    assert [title.value for title in app.title] == ["PDF 轉圖片"]
    convert_buttons = [
        button for button in app.button if button.label == "轉換並建立 ZIP"
    ]
    assert len(convert_buttons) == 1
    assert convert_buttons[0].disabled


def test_pdf_to_images_page_converts_multiple_files() -> None:
    app = image_page_with_items(
        [
            {
                "id": "first",
                "name": "掃描.pdf",
                "data": make_pdf(72, 72),
                "page_count": 1,
                "error": None,
            },
            {
                "id": "second",
                "name": "掃描.PDF",
                "data": make_pdf(72, 144),
                "page_count": 1,
                "error": None,
            },
        ]
    )

    convert_button = next(
        button for button in app.button if button.label == "轉換並建立 ZIP"
    )
    assert not convert_button.disabled
    convert_button.click().run(timeout=10)

    assert not app.exception
    result = app.session_state["image_result"]
    assert result["pdf_count"] == 2
    assert result["image_count"] == 2
    assert result["data"].startswith(b"PK")
    assert [message.value for message in app.success] == [
        "轉換完成：2 份 PDF，共 2 張圖片。"
    ]
    assert [button.label for button in app.download_button] == ["下載圖片 ZIP"]


def test_pdf_to_images_grid_changes_invalidate_result_and_refresh_auto_name(
    monkeypatch,
) -> None:
    state = SimpleNamespace(
        image_pdf_items=[
            {"id": "first", "name": "第一.pdf"},
            {"id": "second", "name": "第二.pdf"},
        ],
        image_upload_error="old",
        image_result={"data": b"old"},
        image_zip_name="pdf-images.zip",
        image_auto_zip_name="pdf-images.zip",
    )
    monkeypatch.setattr(images_ui.st, "session_state", state)

    images_ui._apply_grid_event(PDFGridEvent(action="remove", item_id="second"))

    assert [item["id"] for item in state.image_pdf_items] == ["first"]
    assert state.image_result is None
    assert state.image_upload_error is None
    assert state.image_zip_name == "第一-images.zip"


def test_browser_shutdown_monitor_waits_for_health_then_shows_closed_state() -> None:
    assert "/_stcore/health" in SHUTDOWN_MONITOR_HTML
    assert "hasBeenHealthy" in SHUTDOWN_MONITOR_HTML
    assert "consecutiveFailures >= 3" in SHUTDOWN_MONITOR_HTML
    assert "本機 PDF 工具箱已關閉" in SHUTDOWN_MONITOR_HTML
    assert "window.close" not in SHUTDOWN_MONITOR_HTML


def test_shutdown_monitor_uses_current_non_iframe_streamlit_api(monkeypatch) -> None:
    from pdf_toolbox.ui import shutdown_notice

    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        shutdown_notice.st,
        "html",
        lambda body, *, unsafe_allow_javascript=False: calls.append(
            (body, unsafe_allow_javascript)
        ),
    )

    shutdown_notice.render_shutdown_monitor()

    assert calls == [(SHUTDOWN_MONITOR_HTML, True)]


def test_merge_page_merges_in_display_order() -> None:
    app = merge_page_with_items(
        [
            {
                "id": "second",
                "name": "文件.pdf",
                "data": make_pdf(300, 400),
                "page_count": 1,
                "error": None,
            },
            {
                "id": "first",
                "name": "文件.pdf",
                "data": make_pdf(100, 200),
                "page_count": 1,
                "error": None,
            },
        ]
    )

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


def test_grid_remove_event_and_clear_all(monkeypatch) -> None:
    state = SimpleNamespace(
        pdf_items=[
            {"id": "first", "data": b"1"},
            {"id": "second", "data": b"2"},
            {"id": "third", "data": b"3"},
        ],
        upload_error="old error",
        merged_result={"data": b"old"},
    )
    monkeypatch.setattr(merge_ui.st, "session_state", state)

    merge_ui._apply_grid_event(PDFGridEvent(action="remove", item_id="second"))

    assert [item["id"] for item in state.pdf_items] == ["first", "third"]
    assert state.upload_error is None
    assert state.merged_result is None
    monkeypatch.undo()

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
                "id": "third",
                "name": "第三.pdf",
                "data": make_pdf(300, 400),
                "page_count": 1,
                "error": None,
            },
        ]
    )

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


def test_grid_event_reorders_the_same_list_used_for_merging(monkeypatch) -> None:
    state = SimpleNamespace(
        pdf_items=[
            {"id": "first"},
            {"id": "second"},
            {"id": "third"},
        ],
        upload_error=None,
        merged_result={"data": b"old"},
    )
    monkeypatch.setattr(merge_ui.st, "session_state", state)
    event = PDFGridEvent(
        action="reorder",
        ordered_ids=("second", "third", "first"),
    )

    merge_ui._apply_grid_event(event)

    assert [item["id"] for item in state.pdf_items] == ["second", "third", "first"]
    assert state.merged_result is None
