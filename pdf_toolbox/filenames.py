"""Filename helpers shared by PDF features."""


def sanitize_pdf_filename(value: str, *, fallback: str = "output") -> str:
    """Return a Windows-safe filename ending in .pdf."""

    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid or ord(char) < 32 else char for char in value)
    cleaned = cleaned.strip().rstrip(". ")
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4].rstrip(". ")
    if not cleaned:
        cleaned = fallback
    return f"{cleaned}.pdf"

