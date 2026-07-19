from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image
from pypdf import PdfWriter

from pdf_toolbox.errors import PDFToImagesError
from pdf_toolbox.features import pdf_to_images
from pdf_toolbox.features.pdf_to_images import convert_pdfs_to_images
from pdf_toolbox.filenames import (
    pdf_filename_stem,
    sanitize_zip_filename,
    unique_pdf_stems,
)


def make_pdf(
    name: str,
    sizes: list[tuple[float, float]],
    rotations: list[int] | None = None,
    *,
    password: str | None = None,
) -> BytesIO:
    writer = PdfWriter()
    rotations = rotations or [0] * len(sizes)
    for (width, height), rotation in zip(sizes, rotations, strict=True):
        page = writer.add_blank_page(width=width, height=height)
        if rotation:
            page.rotate(rotation)
    if password:
        writer.encrypt(password)
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    stream.seek(0)
    stream.name = name  # type: ignore[attr-defined]
    return stream


def archive_entries(data: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_filename_rules_preserve_unicode_and_resolve_casefold_collisions() -> None:
    assert pdf_filename_stem(" 中文 文件.PDF ") == "中文 文件"
    assert pdf_filename_stem('bad<>:"/\\|?*.pdf') == "bad_________"
    assert pdf_filename_stem(" ... .pdf") == "document"
    assert unique_pdf_stems(
        ["報告.PDF", "報告.pdf", "REPORT.pdf", "report.PDF", "報告-2.pdf"]
    ) == ["報告", "報告-2", "REPORT", "report-2", "報告-2-2"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("圖片結果", "圖片結果.zip"),
        ("圖片結果.ZIP", "圖片結果.zip"),
        ('bad<>:"/\\|?*.zip', "bad_________.zip"),
        (" . ", "pdf-images.zip"),
    ],
)
def test_zip_filename_is_safe_and_has_extension(raw: str, expected: str) -> None:
    assert sanitize_zip_filename(raw) == expected


def test_multiple_pdfs_convert_to_png_subfolders_with_stable_names() -> None:
    first = make_pdf("掃描 文件.pdf", [(72, 144), (144, 72)])
    second = make_pdf("掃描 文件.PDF", [(72, 72)])

    result = convert_pdfs_to_images([first, second], image_format="png", dpi=150)
    try:
        entries = archive_entries(result.archive.getvalue())
        assert list(entries) == [
            "掃描 文件/掃描 文件-001.png",
            "掃描 文件/掃描 文件-002.png",
            "掃描 文件-2/掃描 文件-2-001.png",
        ]
        assert result.image_count == 3
        assert result.pdf_count == 2
        with Image.open(BytesIO(entries["掃描 文件/掃描 文件-001.png"])) as image:
            assert image.format == "PNG"
            assert image.size == (150, 300)
        with Image.open(BytesIO(entries["掃描 文件/掃描 文件-002.png"])) as image:
            assert image.size == (300, 150)
    finally:
        result.archive.close()
        first.close()
        second.close()


def test_flat_jpeg_output_uses_jpg_extension_and_respects_rotation() -> None:
    source = make_pdf("scan.pdf", [(72, 144)], [90])

    result = convert_pdfs_to_images(
        [source],
        image_format="jpg",
        dpi=150,
        jpeg_quality=82,
        use_subfolders=False,
    )
    try:
        entries = archive_entries(result.archive.getvalue())
        assert list(entries) == ["scan-001.jpg"]
        with Image.open(BytesIO(entries["scan-001.jpg"])) as image:
            assert image.format == "JPEG"
            assert image.size == (300, 150)
    finally:
        result.archive.close()
        source.close()


def test_progress_reports_every_page_in_order() -> None:
    source = make_pdf("進度.pdf", [(72, 72), (72, 72)])
    calls: list[tuple[int, int, str, int]] = []

    result = convert_pdfs_to_images(
        [source],
        dpi=150,
        progress=lambda done, total, name, page: calls.append(
            (done, total, name, page)
        ),
    )
    try:
        assert calls == [
            (1, 2, "進度.pdf", 1),
            (2, 2, "進度.pdf", 2),
        ]
    finally:
        result.archive.close()
        source.close()


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (BytesIO(b""), "不是有效的 PDF"),
        (BytesIO(b"not a pdf"), "不是有效的 PDF"),
        (BytesIO(b"%PDF-1.7\nbroken"), "可能已損壞"),
    ],
)
def test_invalid_input_is_rejected_without_a_result(
    source: BytesIO,
    message: str,
) -> None:
    source.name = "損壞.pdf"  # type: ignore[attr-defined]
    with pytest.raises(PDFToImagesError, match=message):
        convert_pdfs_to_images([source])


def test_encrypted_input_is_rejected_with_its_filename() -> None:
    protected = make_pdf("機密.pdf", [(72, 72)], password="secret")
    with pytest.raises(PDFToImagesError, match="機密.pdf.*密碼保護"):
        convert_pdfs_to_images([protected])
    protected.close()


def test_entire_batch_is_validated_before_rendering(monkeypatch) -> None:
    valid = make_pdf("有效.pdf", [(72, 72)])
    invalid = BytesIO(b"not a pdf")
    invalid.name = "無效.pdf"  # type: ignore[attr-defined]
    opened_documents: list[bytes] = []
    monkeypatch.setattr(
        pdf_to_images.pdfium,
        "PdfDocument",
        lambda data: opened_documents.append(data),
    )

    with pytest.raises(PDFToImagesError, match="無效.pdf"):
        convert_pdfs_to_images([valid, invalid])

    assert opened_documents == []
    valid.close()
    invalid.close()


def test_render_pixel_limit_names_source_and_page(monkeypatch) -> None:
    source = make_pdf("超大頁.pdf", [(72, 72)])
    monkeypatch.setattr(pdf_to_images, "MAX_RENDER_PIXELS", 100)

    with pytest.raises(PDFToImagesError, match="超大頁.pdf.*第 1 頁.*降低解析度"):
        convert_pdfs_to_images([source], dpi=150)

    source.close()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"image_format": "webp"}, "PNG 或 JPEG"),
        ({"dpi": 72}, "150、200 或 300"),
        ({"jpeg_quality": 59}, "60 到 100"),
    ],
)
def test_rejects_unsupported_options(kwargs: dict[str, object], message: str) -> None:
    source = make_pdf("選項.pdf", [(72, 72)])
    with pytest.raises(PDFToImagesError, match=message):
        convert_pdfs_to_images([source], **kwargs)  # type: ignore[arg-type]
    source.close()


def test_page_number_expands_beyond_three_digits() -> None:
    assert pdf_to_images._page_entry_name(
        "scan", 7, 1000, "png", use_subfolders=False
    ) == "scan-0007.png"
