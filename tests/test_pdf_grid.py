import base64
from types import SimpleNamespace

from pdf_toolbox.ui import pdf_grid


def item(item_id: str, *, thumbnail: bytes | None = b"\x89PNG") -> dict:
    return {
        "id": item_id,
        "name": f"{item_id}.pdf",
        "data": b"pdf bytes",
        "page_count": 2,
        "thumbnail": thumbnail,
        "error": None,
    }


def component_result(monkeypatch, raw: dict):
    captured: dict = {}

    def component(**kwargs):
        captured.update(kwargs)
        return raw

    monkeypatch.setattr(pdf_grid, "_component_func", component)
    monkeypatch.setattr(pdf_grid.st, "session_state", {})
    return captured


def test_pdf_grid_returns_validated_complete_order(monkeypatch) -> None:
    raw = {
        "action": "reorder",
        "ordered_ids": ["second", "first"],
        "event_id": "event-1",
    }
    captured = component_result(monkeypatch, raw)

    event = pdf_grid.render_pdf_grid([item("first"), item("second")])

    assert event is not None
    assert event.action == "reorder"
    assert event.ordered_ids == ("second", "first")
    assert captured["items"][0]["thumbnail_url"] == (
        "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode("ascii")
    )


def test_pdf_grid_rejects_incomplete_or_forged_order(monkeypatch) -> None:
    component_result(
        monkeypatch,
        {
            "action": "reorder",
            "ordered_ids": ["first", "unknown"],
            "event_id": "event-2",
        },
    )

    assert pdf_grid.render_pdf_grid([item("first"), item("second")]) is None


def test_pdf_grid_returns_remove_once(monkeypatch) -> None:
    raw = {
        "action": "remove",
        "item_id": "second",
        "event_id": "event-3",
    }
    component_result(monkeypatch, raw)
    items = [item("first"), item("second")]

    event = pdf_grid.render_pdf_grid(items)
    repeated = pdf_grid.render_pdf_grid(items)

    assert event is not None
    assert event.action == "remove"
    assert event.item_id == "second"
    assert repeated is None


def test_pdf_grid_frontend_is_offline_responsive_and_two_dimensional() -> None:
    frontend = pdf_grid.PDF_GRID_FRONTEND
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(frontend.iterdir())
        if path.is_file()
    )

    assert "grid-template-columns: repeat(auto-fill" in combined
    assert "insertionReference" in combined
    assert "ordered_ids" in combined
    assert "maxHeight" in combined
    assert '"PDF 文件清單"' in combined
    assert "http://" not in combined
    assert "https://" not in combined
