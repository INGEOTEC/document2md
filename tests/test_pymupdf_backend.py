import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

from document2md.pymupdf_backend import (
    _require_pymupdf,
    convert_to_markdown,
    has_text_layer,
)

# A paragraph long enough to clear MIN_CHARS_PER_PAGE (50 non-whitespace chars).
_PARAGRAPH = "This page carries real embedded text, not a scanned image of a page."


def _make_pdf(path: Path, texts: list[str | None]) -> None:
    """Build a PDF at `path` with one page per entry in `texts`: a string
    inserts that text on the page, `None` leaves it blank."""
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        if text is not None:
            page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


class TestHasTextLayer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.tmpdir.name) / "doc.pdf"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_true_when_every_page_has_text(self):
        _make_pdf(self.pdf_path, [_PARAGRAPH, _PARAGRAPH, _PARAGRAPH])
        self.assertTrue(has_text_layer(self.pdf_path))

    def test_false_when_every_page_is_blank(self):
        _make_pdf(self.pdf_path, [None, None, None])
        self.assertFalse(has_text_layer(self.pdf_path))

    def test_true_at_the_08_threshold(self):
        # 4/5 = 0.8, exactly the MIN_TEXT_PAGE_FRACTION threshold.
        _make_pdf(self.pdf_path, [_PARAGRAPH, _PARAGRAPH, _PARAGRAPH, _PARAGRAPH, None])
        self.assertTrue(has_text_layer(self.pdf_path))

    def test_false_below_the_08_threshold(self):
        # 3/5 = 0.6, below the threshold.
        _make_pdf(self.pdf_path, [_PARAGRAPH, _PARAGRAPH, _PARAGRAPH, None, None])
        self.assertFalse(has_text_layer(self.pdf_path))


class TestConvertToMarkdown(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.tmpdir.name) / "doc.pdf"
        self.md_path = Path(self.tmpdir.name) / "doc.md"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_non_empty_markdown_with_the_inserted_text(self):
        _make_pdf(self.pdf_path, [_PARAGRAPH])
        convert_to_markdown(self.pdf_path, self.md_path)

        text = self.md_path.read_text(encoding="utf-8")
        self.assertIn("embedded text", text)
        self.assertTrue(text.endswith("\n"))


class TestRequirePymupdf(unittest.TestCase):
    def test_raises_when_pymupdf4llm_missing(self):
        with patch("importlib.util.find_spec", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                _require_pymupdf()
        self.assertIn("pip install document2md", str(ctx.exception))

    def test_does_not_raise_when_installed(self):
        _require_pymupdf()


if __name__ == "__main__":
    unittest.main()
