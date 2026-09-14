"""Convert a born-digital PDF (one that already carries an embedded text
layer) to Markdown by reading that text layer directly with `pymupdf4llm`,
instead of running mineru's OCR/layout models on it. Orders of magnitude
faster than the mineru backend and needs no models, at the cost of slightly
worse structure; mineru remains the reference backend where it is installed
(see document2md.batch.BatchConverter's `auto` resolution).

PyMuPDF and pymupdf4llm are AGPL-3.0 licensed; document2md itself stays
Apache-2.0 (see the README's Install section).

`pymupdf`/`pymupdf4llm` are imported inside the functions below, never at
module level, so this module can still be imported (for autodoc, or by
BatchConverter probing `has_text_layer`) when the package is installed with
`--no-deps` and neither is present.
"""
from pathlib import Path

# A page counts as text-bearing when its extracted text has at least this
# many non-whitespace characters.
MIN_CHARS_PER_PAGE = 50

# The PDF as a whole counts as having a text layer when at least this
# fraction of its pages are text-bearing — tolerating a few scanned inserts
# in an otherwise born-digital document.
MIN_TEXT_PAGE_FRACTION = 0.8


def _require_pymupdf() -> None:
    """Raise RuntimeError with an actionable message if `pymupdf4llm` isn't
    installed, instead of letting the `import` inside convert_to_markdown
    fail opaquely."""
    import importlib.util

    if importlib.util.find_spec("pymupdf4llm") is None:
        raise RuntimeError(
            "'pymupdf4llm' is required for the pymupdf backend but isn't "
            "installed. Install it with: pip install document2md"
        )


def has_text_layer(pdf_path: Path) -> bool:
    """Whether `pdf_path` is born-digital enough for the pymupdf backend:
    at least MIN_TEXT_PAGE_FRACTION of its pages each have at least
    MIN_CHARS_PER_PAGE non-whitespace characters of extractable text.
    A fully scanned PDF fails; a mostly-digital document with a few scanned
    inserts still passes."""
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        if doc.page_count == 0:
            return False
        text_pages = sum(
            1 for page in doc
            if len("".join(page.get_text().split())) >= MIN_CHARS_PER_PAGE
        )
        return text_pages / doc.page_count >= MIN_TEXT_PAGE_FRACTION


def convert_to_markdown(pdf_path: Path, md_path: Path) -> None:
    """Convert a born-digital PDF to Markdown by extracting its embedded
    text layer with pymupdf4llm — headings inferred from font sizes,
    Markdown tables via PyMuPDF's table finder, reading order handled —
    instead of running mineru's OCR/layout models on it.

    Images are not extracted (no `<md stem>_images/` directory is produced),
    unlike the mineru backend."""
    import pymupdf4llm

    md_text = pymupdf4llm.to_markdown(str(pdf_path), write_images=False)
    md_path.write_text(md_text + "\n", encoding="utf-8")
