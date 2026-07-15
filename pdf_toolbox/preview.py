"""In-memory first-page thumbnail rendering for PDF cards."""

from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium

from pdf_toolbox.errors import PDFPreviewError


DEFAULT_THUMBNAIL_WIDTH = 220
MAX_THUMBNAIL_HEIGHT = 400


def render_first_page_thumbnail(
    data: bytes,
    filename: str,
    *,
    width: int = DEFAULT_THUMBNAIL_WIDTH,
) -> bytes:
    """Render the first PDF page as compressed PNG bytes without using disk."""

    if width <= 0:
        raise ValueError("縮圖寬度必須大於 0。")

    document = None
    page = None
    bitmap = None
    image = None
    output = BytesIO()
    try:
        document = pdfium.PdfDocument(data)
        if len(document) == 0:
            raise PDFPreviewError(f"「{filename}」沒有可預覽的頁面。")

        page = document[0]
        page_width, page_height = page.get_size()
        if page_width <= 0 or page_height <= 0:
            raise PDFPreviewError(f"「{filename}」的第一頁尺寸無效。")

        scale = min(width / page_width, MAX_THUMBNAIL_HEIGHT / page_height)
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()
    except PDFPreviewError:
        raise
    except Exception as exc:
        raise PDFPreviewError(f"無法產生「{filename}」的第一頁預覽。") from exc
    finally:
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        if document is not None:
            document.close()
        output.close()
