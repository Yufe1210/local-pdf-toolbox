"""Filename helpers shared by PDF features."""


def sanitize_filename_stem(value: str, *, fallback: str = "document") -> str:
    """Return a Windows-safe filename stem while preserving readable Unicode."""

    invalid = '<>:"/\\|?*'
    cleaned = "".join(
        "_" if char in invalid or ord(char) < 32 else char
        for char in value
    )
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def pdf_filename_stem(value: str, *, fallback: str = "document") -> str:
    """Remove a PDF suffix and return a safe output stem."""

    candidate = value.strip().rstrip(" .")
    if candidate.casefold().endswith(".pdf"):
        candidate = candidate[:-4]
    return sanitize_filename_stem(candidate, fallback=fallback)


def unique_pdf_stems(names: list[str]) -> list[str]:
    """Return stable, case-insensitively unique stems in input order."""

    used: set[str] = set()
    result: list[str] = []
    for name in names:
        base = pdf_filename_stem(name)
        candidate = base
        suffix = 2
        while candidate.casefold() in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate.casefold())
        result.append(candidate)
    return result


def sanitize_zip_filename(value: str, *, fallback: str = "pdf-images") -> str:
    """Return a Windows-safe filename ending in .zip."""

    candidate = value.strip().rstrip(" .")
    if candidate.casefold().endswith(".zip"):
        candidate = candidate[:-4]
    return f"{sanitize_filename_stem(candidate, fallback=fallback)}.zip"


def sanitize_pdf_filename(value: str, *, fallback: str = "output") -> str:
    """Return a Windows-safe filename ending in .pdf."""

    cleaned = value.strip().rstrip(" .")
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4]
    return f"{sanitize_filename_stem(cleaned, fallback=fallback)}.pdf"
