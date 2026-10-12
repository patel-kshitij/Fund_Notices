"""Read the text out of a PDF. Every later step works on this text, never on the PDF."""

import io
from pathlib import Path

from pypdf import PdfReader


def pdf_text(source: Path | bytes) -> str:
    """Return the text of every page, with pages separated by a blank line."""
    data = source.read_bytes() if isinstance(source, Path) else source
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(page.extract_text() for page in reader.pages)
