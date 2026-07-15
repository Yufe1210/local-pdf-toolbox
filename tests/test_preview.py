from io import BytesIO

from PIL import Image
from pypdf import PdfWriter

from pdf_toolbox import preview
from pdf_toolbox.errors import PDFPreviewError
from pdf_toolbox.preview import render_first_page_thumbnail


def make_pdf(width: float, height: float, *, rotation: int = 0) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    if rotation:
        page.rotate(rotation)
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    return stream.getvalue()


def test_thumbnail_is_png_with_requested_width_and_page_orientation() -> None:
    thumbnail = render_first_page_thumbnail(
        make_pdf(200, 400),
        "直向.pdf",
        width=200,
    )

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.format == "PNG"
        assert image.width == 200
        assert image.height == 400


def test_thumbnail_respects_intrinsic_page_rotation() -> None:
    thumbnail = render_first_page_thumbnail(
        make_pdf(200, 400, rotation=90),
        "旋轉.pdf",
        width=200,
    )

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.width == 200
        assert image.height == 100


def test_thumbnail_caps_extreme_page_height_to_control_bitmap_memory() -> None:
    thumbnail = render_first_page_thumbnail(
        make_pdf(10, 1000),
        "超長頁面.pdf",
        width=220,
    )

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.width == 4
        assert image.height == 400


def test_pdfium_resources_are_closed_after_each_thumbnail(monkeypatch) -> None:
    events: list[str] = []

    class FakeImage:
        def save(self, output, **_kwargs) -> None:
            output.write(b"\x89PNG\r\n\x1a\n")

        def close(self) -> None:
            events.append("image")

    class FakeBitmap:
        def to_pil(self):
            return FakeImage()

        def close(self) -> None:
            events.append("bitmap")

    class FakePage:
        def get_size(self):
            return 100, 200

        def render(self, **_kwargs):
            return FakeBitmap()

        def close(self) -> None:
            events.append("page")

    class FakeDocument:
        def __len__(self) -> int:
            return 1

        def __getitem__(self, _index: int):
            return FakePage()

        def close(self) -> None:
            events.append("document")

    monkeypatch.setattr(preview.pdfium, "PdfDocument", lambda _data: FakeDocument())

    assert render_first_page_thumbnail(b"pdf", "資源.pdf").startswith(b"\x89PNG")
    assert events == ["image", "bitmap", "page", "document"]


def test_pdfium_resources_are_closed_when_rendering_fails(monkeypatch) -> None:
    events: list[str] = []

    class FailingBitmap:
        def to_pil(self):
            raise RuntimeError("render failed")

        def close(self) -> None:
            events.append("bitmap")

    class FakePage:
        def get_size(self):
            return 100, 200

        def render(self, **_kwargs):
            return FailingBitmap()

        def close(self) -> None:
            events.append("page")

    class FakeDocument:
        def __len__(self) -> int:
            return 1

        def __getitem__(self, _index: int):
            return FakePage()

        def close(self) -> None:
            events.append("document")

    monkeypatch.setattr(preview.pdfium, "PdfDocument", lambda _data: FakeDocument())

    try:
        render_first_page_thumbnail(b"pdf", "失敗.pdf")
    except PDFPreviewError:
        pass
    else:
        raise AssertionError("預覽失敗時應回報 PDFPreviewError")
    assert events == ["bitmap", "page", "document"]
