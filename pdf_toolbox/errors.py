"""User-facing application errors."""


class PDFToolError(ValueError):
    """Base class for errors that can be shown directly to users."""


class PDFMergeError(PDFToolError):
    """Raised when one or more PDF files cannot be merged."""


class PDFPreviewError(PDFToolError):
    """Raised when the first page of a PDF cannot be rendered safely."""


class PDFToImagesError(PDFToolError):
    """Raised when one or more PDFs cannot be converted to images."""
