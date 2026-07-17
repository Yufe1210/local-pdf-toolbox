"""Responsive PDF card grid implemented as an offline Streamlit component."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import streamlit as st
import streamlit.components.v1 as components


PDF_GRID_FRONTEND = Path(__file__).with_name("pdf_grid_frontend")
_component_func = None


@dataclass(frozen=True, slots=True)
class PDFGridEvent:
    """One validated action reported by the browser-side PDF grid."""

    action: Literal["reorder", "remove"]
    ordered_ids: tuple[str, ...] = ()
    item_id: str | None = None


def _get_component():
    global _component_func  # noqa: PLW0603
    if _component_func is None:
        _component_func = components.declare_component(
            "pdf_sortable_grid",
            path=str(PDF_GRID_FRONTEND),
        )
    return _component_func


def _card_payload(item: dict[str, Any]) -> dict[str, Any]:
    thumbnail = item.get("thumbnail")
    thumbnail_url = (
        "data:image/png;base64," + base64.b64encode(thumbnail).decode("ascii")
        if thumbnail
        else None
    )
    page_count = item.get("page_count")
    return {
        "id": str(item["id"]),
        "name": str(item["name"]),
        "page_count": int(page_count) if page_count is not None else None,
        "size_mb": round(len(item["data"]) / 1024 / 1024, 1),
        "thumbnail_url": thumbnail_url,
        "error": str(item["error"]) if item.get("error") else None,
    }


def render_pdf_grid(
    items: Sequence[dict[str, Any]],
    *,
    key: str = "pdf_card_grid",
) -> PDFGridEvent | None:
    """Render the responsive grid and return each browser action once."""

    raw = _get_component()(
        items=[_card_payload(item) for item in items],
        key=key,
        default=None,
    )
    if not isinstance(raw, dict):
        return None

    event_id = raw.get("event_id")
    if not isinstance(event_id, str):
        return None
    seen_key = f"_pdf_grid_seen_{key}"
    if st.session_state.get(seen_key) == event_id:
        return None
    st.session_state[seen_key] = event_id

    current_ids = tuple(str(item["id"]) for item in items)
    action = raw.get("action")
    if action == "reorder":
        ordered_ids = tuple(raw.get("ordered_ids", ()))
        if (
            len(ordered_ids) != len(current_ids)
            or len(set(ordered_ids)) != len(ordered_ids)
            or set(ordered_ids) != set(current_ids)
        ):
            return None
        return PDFGridEvent(action="reorder", ordered_ids=ordered_ids)

    if action == "remove":
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or item_id not in current_ids:
            return None
        return PDFGridEvent(action="remove", item_id=item_id)

    return None
