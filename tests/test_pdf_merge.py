from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions

from pdf_merge import PDFMergeError, inspect_pdf, merge_pdfs, sanitize_output_filename


def make_pdf(
    name: str,
    sizes: list[tuple[float, float]],
    rotations: list[int] | None = None,
    password: str | None = None,
    owner_password: str | None = None,
    permissions: UserAccessPermissions | None = None,
) -> BytesIO:
    writer = PdfWriter()
    rotations = rotations or [0] * len(sizes)
    for (width, height), rotation in zip(sizes, rotations, strict=True):
        page = writer.add_blank_page(width=width, height=height)
        if rotation:
            page.rotate(rotation)
    if password is not None or owner_password is not None:
        encrypt_options = {"owner_password": owner_password}
        if permissions is not None:
            encrypt_options["permissions_flag"] = permissions
        writer.encrypt(password or "", **encrypt_options)  # type: ignore[arg-type]
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    stream.seek(0)
    stream.name = name  # type: ignore[attr-defined]
    return stream


def test_merge_preserves_order_sizes_and_rotation() -> None:
    first = make_pdf("第一份.pdf", [(100, 200), (110, 210)], [0, 90])
    second = make_pdf("第二份.pdf", [(300, 400)])

    output = merge_pdfs([first, second])
    reader = PdfReader(output)

    assert len(reader.pages) == 3
    assert [float(page.mediabox.width) for page in reader.pages] == [100, 110, 300]
    assert [float(page.mediabox.height) for page in reader.pages] == [200, 210, 400]
    assert [page.rotation for page in reader.pages] == [0, 90, 0]


def test_duplicate_chinese_filenames_are_supported() -> None:
    first = make_pdf("文件.pdf", [(100, 100)])
    second = make_pdf("文件.pdf", [(200, 200)])

    output = merge_pdfs([first, second])

    assert len(PdfReader(output).pages) == 2


def test_requires_at_least_two_files() -> None:
    with pytest.raises(PDFMergeError, match="至少選擇 2 個"):
        merge_pdfs([make_pdf("only.pdf", [(100, 100)])])


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("empty.pdf", b"", "不是有效的 PDF"),
        ("fake.pdf", b"this is not a pdf", "不是有效的 PDF"),
        ("broken.pdf", b"%PDF-1.7\nbroken", "可能已損壞"),
    ],
)
def test_rejects_invalid_input(name: str, content: bytes, message: str) -> None:
    stream = BytesIO(content)
    stream.name = name  # type: ignore[attr-defined]

    with pytest.raises(PDFMergeError, match=message):
        inspect_pdf(stream)


def test_rejects_encrypted_pdf_with_filename() -> None:
    protected = make_pdf("機密.pdf", [(100, 100)], password="secret")

    with pytest.raises(PDFMergeError, match="機密.pdf.*需要密碼"):
        inspect_pdf(protected)


def test_empty_user_password_and_restrictive_permissions_are_supported() -> None:
    protected = make_pdf(
        "可直接開啟.pdf",
        [(100, 200)],
        password="",
        owner_password="owner-secret",
        permissions=UserAccessPermissions.PRINT,
    )
    normal = make_pdf("一般.pdf", [(300, 400)])

    info = inspect_pdf(protected)
    output = merge_pdfs([protected, normal])

    assert info.page_count == 1
    assert len(PdfReader(output).pages) == 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("報告", "報告.pdf"),
        ("報告.PDF", "報告.pdf"),
        ('bad<>:"/\\|?*name.pdf', "bad_________name.pdf"),
        (" . ", "merged.pdf"),
    ],
)
def test_sanitize_output_filename(raw: str, expected: str) -> None:
    assert sanitize_output_filename(raw) == expected
