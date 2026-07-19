"""Convert complete PDF pages to images inside an in-memory ZIP archive."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from math import ceil
from typing import BinaryIO, Literal
from zipfile import ZIP_STORED, ZipFile

import pypdfium2 as pdfium

from pdf_toolbox.errors import PDFMergeError, PDFToImagesError
from pdf_toolbox.filenames import unique_pdf_stems
from pdf_toolbox.pdf import display_name, inspect_pdfs, rewind


ImageFormat = Literal["png", "jpg"]
ProgressCallback = Callable[[int, int, str, int], None]

SUPPORTED_DPI = frozenset({150, 200, 300})
MAX_RENDER_PIXELS = 40_000_000


@dataclass(frozen=True, slots=True)
class PDFImagesResult:
    """Completed in-memory archive and conversion statistics."""

    archive: BytesIO
    image_count: int
    pdf_count: int
    entry_names: tuple[str, ...]


def _validate_options(
    image_format: str,
    dpi: int,
    jpeg_quality: int,
) -> ImageFormat:
    normalized_format = image_format.casefold()
    if normalized_format not in {"png", "jpg"}:
        raise PDFToImagesError("圖片格式只支援 PNG 或 JPEG。")
    if dpi not in SUPPORTED_DPI:
        raise PDFToImagesError("解析度只支援 150、200 或 300 DPI。")
    if not 60 <= jpeg_quality <= 100:
        raise PDFToImagesError("JPEG 品質必須介於 60 到 100。")
    return normalized_format  # type: ignore[return-value]


def _page_entry_name(
    stem: str,
    page_number: int,
    page_count: int,
    extension: ImageFormat,
    *,
    use_subfolders: bool,
) -> str:
    digits = max(3, len(str(page_count)))
    filename = f"{stem}-{page_number:0{digits}d}.{extension}"
    return f"{stem}/{filename}" if use_subfolders else filename


def _render_page_image(
    page: pdfium.PdfPage,
    *,
    source_name: str,
    page_number: int,
    image_format: ImageFormat,
    dpi: int,
    jpeg_quality: int,
) -> bytes:
    scale = dpi / 72
    width, height = page.get_size()
    pixel_count = ceil(width * scale) * ceil(height * scale)
    if pixel_count > MAX_RENDER_PIXELS:
        raise PDFToImagesError(
            f"「{source_name}」第 {page_number} 頁在 {dpi} DPI 會超過"
            f" {MAX_RENDER_PIXELS:,} 像素，請降低解析度。"
        )

    bitmap = None
    image = None
    encoded = BytesIO()
    converted_image = None
    try:
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        if image_format == "png":
            image.save(encoded, format="PNG", optimize=True)
        else:
            converted_image = image.convert("RGB")
            converted_image.save(
                encoded,
                format="JPEG",
                quality=jpeg_quality,
                optimize=True,
                subsampling=0,
            )
        return encoded.getvalue()
    except PDFToImagesError:
        raise
    except Exception as exc:
        raise PDFToImagesError(
            f"轉換「{source_name}」第 {page_number} 頁時發生錯誤。"
        ) from exc
    finally:
        if converted_image is not None:
            converted_image.close()
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
        encoded.close()


def convert_pdfs_to_images(
    files: Sequence[BinaryIO],
    *,
    image_format: str = "png",
    dpi: int = 200,
    jpeg_quality: int = 90,
    use_subfolders: bool = True,
    progress: ProgressCallback | None = None,
) -> PDFImagesResult:
    """Render every PDF page and return one ZIP without writing temporary files."""

    normalized_format = _validate_options(image_format, dpi, jpeg_quality)
    try:
        infos = inspect_pdfs(files, minimum=1)
    except PDFMergeError as exc:
        raise PDFToImagesError(str(exc)) from exc

    stems = unique_pdf_stems([info.name for info in infos])
    total_pages = sum(info.page_count for info in infos)
    completed_pages = 0
    entry_names: list[str] = []
    output = BytesIO()

    try:
        with ZipFile(output, mode="w", compression=ZIP_STORED) as archive:
            for index, (file, info, stem) in enumerate(zip(files, infos, stems)):
                document = None
                source_name = display_name(file, index)
                try:
                    rewind(file)
                    pdf_data = file.read()
                    document = pdfium.PdfDocument(pdf_data)
                    if len(document) != info.page_count:
                        raise PDFToImagesError(
                            f"「{source_name}」的頁數在驗證後發生變化，請重新選擇檔案。"
                        )

                    for page_index in range(info.page_count):
                        page = None
                        try:
                            page = document[page_index]
                            image_data = _render_page_image(
                                page,
                                source_name=source_name,
                                page_number=page_index + 1,
                                image_format=normalized_format,
                                dpi=dpi,
                                jpeg_quality=jpeg_quality,
                            )
                            entry_name = _page_entry_name(
                                stem,
                                page_index + 1,
                                info.page_count,
                                normalized_format,
                                use_subfolders=use_subfolders,
                            )
                            archive.writestr(entry_name, image_data)
                            entry_names.append(entry_name)
                            completed_pages += 1
                            if progress is not None:
                                progress(
                                    completed_pages,
                                    total_pages,
                                    source_name,
                                    page_index + 1,
                                )
                        finally:
                            if page is not None:
                                page.close()
                except PDFToImagesError:
                    raise
                except Exception as exc:
                    raise PDFToImagesError(
                        f"轉換「{source_name}」時發生錯誤。"
                    ) from exc
                finally:
                    if document is not None:
                        document.close()
                    try:
                        file.seek(0)
                    except (AttributeError, OSError):
                        pass

        output.seek(0)
        return PDFImagesResult(
            archive=output,
            image_count=completed_pages,
            pdf_count=len(files),
            entry_names=tuple(entry_names),
        )
    except Exception:
        output.close()
        raise
