"""Batch document-to-Markdown conversion, keeping one mineru-api server warm
across many jobs instead of paying its startup (and model-loading) cost once
per document:

    with BatchConverter() as convert:
        for pdf_path, outdir, filename in jobs:
            convert(pdf_path, outdir, filename)

document2md itself has no notion of what a "note" is or where a document came
from — a job is just a PDF (a single path) or a set of scanned page images (a
list of paths), an output directory, and an output filename. Whatever calls
this decides what those mean (a DOF legal provision, or anything else).
"""
import shutil
from pathlib import Path

from document2md import converter as _converter
from document2md import pymupdf_backend as _pymupdf_backend
from document2md.converter import DEFAULT_TIMEOUT_SECONDS
from document2md.cutter import cut_markdown_by_titles
from document2md.mineru_server import ENV_VAR as _MINERU_API_URL_ENV_VAR
from document2md.mineru_server import MineruServer

# Backend names accepted by BatchConverter(backend=...) and --backend.
# "auto" resolves to a concrete backend in __enter__: "mineru" when the
# mineru CLI is on PATH, "pymupdf" otherwise (see __enter__).
BACKENDS = ("auto", "mineru", "pymupdf")

_MINERU_INSTALL_HINT = 'Install the mineru backend with: pip install "document2md[mineru]"'


class BatchConverter:
    """Context manager: `__enter__` resolves the requested `backend`, starts
    a persistent `mineru-api` server if the resolved backend needs one
    (skipped if a caller further up already has one running via
    MINERU_API_URL), and returns `self`, callable once per document;
    `__exit__` stops it. Calling it converts one document — a single PDF
    path, or a list of image paths for a document spanning several scanned
    pages — to Markdown, written to `outdir/filename`.

    `backend` names who is responsible for the conversion: `"auto"`
    (default), `"mineru"` or `"pymupdf"`; any other value raises
    `ValueError`. `"auto"` resolves to `"mineru"` when the `mineru` CLI is on
    `PATH`, otherwise to `"pymupdf"` — mineru remains the reference backend
    where it is installed; the light backend only makes installing it
    optional. The resolved name is stored as `self.backend` once `__enter__`
    has run.

    `"pymupdf"` reads a PDF's own embedded text layer instead of running
    OCR — far faster, at the cost of slightly worse structure — and raises
    `RuntimeError` (naming the `mineru` extra) on input it cannot handle: a
    list of page images (which always need OCR), or a PDF without enough of
    a text layer (see `document2md.pymupdf_backend.has_text_layer`). There is
    no silent fallback to mineru.

    `titulo`/`titulo_siguiente`, when given, slice the OCR'd Markdown down
    to the text between their two boundaries (see
    document2md.cutter.cut_markdown_by_titles) — e.g. a DOF legal provision's own
    title and the next one's, to cut a page shared with the notes before and
    after it down to just this one. Left out (the default), the whole
    conversion is kept as-is, on the assumption that the whole document is
    what was asked for.
    """

    def __init__(self, backend: str = "auto"):
        """Create an unstarted converter for the requested `backend`
        (`"auto"`, `"mineru"` or `"pymupdf"`; anything else raises
        `ValueError`); call `__enter__` (or use as a context manager) before
        calling it."""
        if backend not in BACKENDS:
            raise ValueError(
                f"Unknown backend {backend!r}; accepted values: {', '.join(BACKENDS)}"
            )
        self._requested_backend = backend
        self.backend: str | None = None
        self._server: MineruServer | None = None

    def __enter__(self) -> "BatchConverter":
        """Resolve the requested backend (storing it as `self.backend`),
        start a persistent `mineru-api` server if it needs one — unless one
        is already reachable via MINERU_API_URL — and return `self`.

        `"auto"` resolves to `"mineru"` when the `mineru` CLI is on `PATH`,
        otherwise to `"pymupdf"`. Raises RuntimeError if the resolved
        backend's dependency isn't installed; this happens here, before any
        document is converted, rather than on the first call."""
        import os

        if self._requested_backend == "auto":
            self.backend = "mineru" if shutil.which("mineru") is not None else "pymupdf"
        else:
            self.backend = self._requested_backend

        if self.backend == "mineru":
            _converter._require_mineru()
            if _MINERU_API_URL_ENV_VAR not in os.environ:
                self._server = MineruServer()
                self._server.start()
        else:
            _pymupdf_backend._require_pymupdf()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Stop the `mineru-api` server started by `__enter__`, if any."""
        if self._server is not None:
            self._server.stop()
            self._server = None

    def __call__(
        self,
        path_or_paths: str | Path | list[str | Path],
        outdir: str | Path,
        filename: str,
        titulo: str | None = None,
        titulo_siguiente: str | None = None,
        *,
        min_confidence: float = 0.6,
        keep_pages: bool = False,
        keep_mineru_output: bool = False,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Path:
        """Convert one document — `path_or_paths` a single PDF path, or a
        list of image paths for a document spanning several scanned pages —
        to Markdown, written to `outdir/filename`, and return that path.

        `titulo`/`titulo_siguiente`, `min_confidence` and `keep_pages` are
        forwarded to `cutter.cut_markdown_by_titles` to crop the result down
        to a single note; left as `None` (the default), the whole conversion
        is kept as-is. `keep_mineru_output` and `timeout` are forwarded to
        `converter.convert_to_markdown`/`convert_images_to_markdown` for the
        `mineru` backend; both are accepted but ignored for `pymupdf`, which
        needs neither.

        Under the `pymupdf` backend, a list of page images (which always
        need OCR) or a PDF without enough of an embedded text layer (see
        `pymupdf_backend.has_text_layer`) raise `RuntimeError` naming the
        `mineru` extra, rather than silently falling back to it."""
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        dest = outdir / filename
        is_image_list = isinstance(path_or_paths, (list, tuple))

        if self.backend == "pymupdf":
            if is_image_list:
                raise RuntimeError(
                    f"Scanned page images always need OCR. {_MINERU_INSTALL_HINT}"
                )
            pdf_path = Path(path_or_paths)
            if not _pymupdf_backend.has_text_layer(pdf_path):
                raise RuntimeError(
                    f"{pdf_path} has no embedded text layer and needs OCR. "
                    f"{_MINERU_INSTALL_HINT}"
                )
            _pymupdf_backend.convert_to_markdown(pdf_path, dest)
        elif is_image_list:
            _converter.convert_images_to_markdown(
                [Path(p) for p in path_or_paths], dest,
                timeout=timeout, keep_mineru_output=keep_mineru_output,
            )
        else:
            _converter.convert_to_markdown(
                Path(path_or_paths), dest,
                timeout=timeout, keep_mineru_output=keep_mineru_output,
            )

        if titulo is None:
            return dest

        full_markdown = dest.read_text(encoding="utf-8")
        if keep_pages:
            (outdir / f"{dest.stem}.full.md").write_text(full_markdown, encoding="utf-8")
        cut = cut_markdown_by_titles(
            full_markdown, titulo, titulo_siguiente, min_confidence=min_confidence
        )
        dest.write_text(cut + "\n", encoding="utf-8")
        return dest
