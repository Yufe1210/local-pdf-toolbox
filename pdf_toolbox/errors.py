"""User-facing application errors."""


class PDFToolError(ValueError):
    """Base class for errors that can be shown directly to users."""


class PDFMergeError(PDFToolError):
    """Raised when one or more PDF files cannot be merged."""

