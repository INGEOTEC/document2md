import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from document2md.cli import main, parse_args


class TestParseArgs(unittest.TestCase):
    def test_defaults(self):
        args = parse_args(["--pdf", "edicion.pdf"])
        self.assertEqual(args.pdf, "edicion.pdf")
        self.assertIsNone(args.images)
        self.assertIsNone(args.filename)
        self.assertEqual(args.outdir, "output")
        self.assertIsNone(args.titulo)
        self.assertIsNone(args.titulo_siguiente)
        self.assertEqual(args.min_confidence, 0.6)
        self.assertFalse(args.keep_pages)
        self.assertFalse(args.keep_mineru_output)
        self.assertEqual(args.backend, "auto")

    def test_images_and_filename_flags(self):
        args = parse_args(["--images", "a.jpg", "b.jpg", "--filename", "out.md"])
        self.assertEqual(args.images, ["a.jpg", "b.jpg"])
        self.assertEqual(args.filename, "out.md")

    def test_custom_outdir(self):
        args = parse_args(["--pdf", "edicion.pdf", "--outdir", "/tmp/my_dof"])
        self.assertEqual(args.outdir, "/tmp/my_dof")

    def test_title_cropping_flags(self):
        args = parse_args([
            "--pdf", "edicion.pdf",
            "--titulo", "ACUERDO por el que...",
            "--titulo-siguiente", "DECRETO por el que...",
            "--min-confidence", "0.8",
            "--keep-pages",
        ])
        self.assertEqual(args.titulo, "ACUERDO por el que...")
        self.assertEqual(args.titulo_siguiente, "DECRETO por el que...")
        self.assertEqual(args.min_confidence, 0.8)
        self.assertTrue(args.keep_pages)

    def test_backend_flag(self):
        args = parse_args(["--pdf", "edicion.pdf", "--backend", "mineru"])
        self.assertEqual(args.backend, "mineru")

    def test_backend_flag_pymupdf(self):
        args = parse_args(["--pdf", "edicion.pdf", "--backend", "pymupdf"])
        self.assertEqual(args.backend, "pymupdf")

    def test_unknown_backend_rejected(self):
        with self.assertRaises(SystemExit):
            parse_args(["--pdf", "edicion.pdf", "--backend", "nope"])


class TestMain(unittest.TestCase):
    def test_main_requires_exactly_one_input_source(self):
        with self.assertRaises(SystemExit):
            main([])
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")
            page_path = Path(tmpdir) / "p1.jpg"
            page_path.write_bytes(b"")
            with self.assertRaises(SystemExit):
                main(["--pdf", str(pdf_path), "--images", str(page_path), "--filename", "out.md"])

    def test_main_requires_filename_with_images(self):
        with self.assertRaises(SystemExit):
            main(["--images", "a.jpg", "b.jpg"])

    def test_main_pdf_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit):
                main(["--pdf", str(Path(tmpdir) / "missing.pdf")])

    def test_main_images_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit):
                main(["--images", str(Path(tmpdir) / "missing.jpg"), "--filename", "out.md"])

    @patch("document2md.cli.BatchConverter")
    def test_main_converts_a_local_pdf(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            main(["--pdf", str(pdf_path), "--outdir", tmpdir])

            mock_convert.assert_called_once_with(
                pdf_path, Path(tmpdir), "edicion.md", None, None,
                min_confidence=0.6, keep_pages=False, keep_mineru_output=False,
            )

    @patch("document2md.cli.BatchConverter")
    def test_main_converts_local_images(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        with tempfile.TemporaryDirectory() as tmpdir:
            page1 = Path(tmpdir) / "p1.jpg"
            page2 = Path(tmpdir) / "p2.jpg"
            page1.write_bytes(b"")
            page2.write_bytes(b"")

            main(["--images", str(page1), str(page2), "--filename", "out.md", "--outdir", tmpdir])

            mock_convert.assert_called_once_with(
                [page1, page2], Path(tmpdir), "out.md", None, None,
                min_confidence=0.6, keep_pages=False, keep_mineru_output=False,
            )

    @patch("document2md.cli.BatchConverter")
    def test_main_passes_keep_mineru_output_flag(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            main(["--pdf", str(pdf_path), "--outdir", tmpdir, "--keep-mineru-output"])

            self.assertTrue(mock_convert.call_args.kwargs["keep_mineru_output"])

    @patch("document2md.cli.BatchConverter")
    def test_main_passes_title_cropping_flags(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            main([
                "--pdf", str(pdf_path), "--outdir", tmpdir,
                "--titulo", "ACUERDO por el que...",
                "--titulo-siguiente", "DECRETO por el que...",
                "--min-confidence", "0.8",
                "--keep-pages",
            ])

            args, kwargs = mock_convert.call_args
            self.assertEqual(args[3], "ACUERDO por el que...")
            self.assertEqual(args[4], "DECRETO por el que...")
            self.assertEqual(kwargs["min_confidence"], 0.8)
            self.assertTrue(kwargs["keep_pages"])

    @patch("document2md.cli.BatchConverter")
    def test_main_exits_clearly_when_conversion_times_out(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        mock_convert.side_effect = subprocess.TimeoutExpired(cmd="mineru", timeout=3600)
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")
            with self.assertRaises(SystemExit):
                main(["--pdf", str(pdf_path), "--outdir", tmpdir])

    @patch("document2md.cli.BatchConverter")
    def test_main_passes_backend_flag(self, mock_batch_converter):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            main(["--pdf", str(pdf_path), "--outdir", tmpdir, "--backend", "mineru"])

            mock_batch_converter.assert_called_once_with(backend="mineru")

    @patch("document2md.cli.BatchConverter")
    def test_main_exits_clearly_when_backend_dependency_missing(self, mock_batch_converter):
        mock_batch_converter.return_value.__enter__.side_effect = RuntimeError(
            "'mineru' is required for the mineru backend but isn't installed. "
            'Install it with: pip install "document2md[mineru]"'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")
            with self.assertRaises(SystemExit) as ctx:
                main(["--pdf", str(pdf_path), "--outdir", tmpdir])

            self.assertIn("document2md[mineru]", str(ctx.exception))

    @patch("document2md.cli.BatchConverter")
    def test_main_prints_resolved_pymupdf_backend(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        mock_convert.backend = "pymupdf"
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["--pdf", str(pdf_path), "--outdir", tmpdir, "--backend", "auto"])

            self.assertIn("Converting to Markdown (pymupdf)...", out.getvalue())

    @patch("document2md.cli.BatchConverter")
    def test_main_exits_clearly_when_pdf_has_no_text_layer(self, mock_batch_converter):
        mock_convert = mock_batch_converter.return_value.__enter__.return_value
        mock_convert.side_effect = RuntimeError(
            "edicion.pdf has no embedded text layer and needs OCR. "
            'Install the mineru backend with: pip install "document2md[mineru]"'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "edicion.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")
            with self.assertRaises(SystemExit) as ctx:
                main(["--pdf", str(pdf_path), "--outdir", tmpdir, "--backend", "pymupdf"])

            self.assertIn("no embedded text layer", str(ctx.exception))
            self.assertIn("document2md[mineru]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
