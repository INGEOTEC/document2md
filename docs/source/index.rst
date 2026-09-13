:mod:`document2md`
==================

.. image:: https://github.com/INGEOTEC/document2md/actions/workflows/test.yml/badge.svg
        :target: https://github.com/INGEOTEC/document2md/actions/workflows/test.yml

.. image:: https://badge.fury.io/py/document2md.svg
        :target: https://badge.fury.io/py/document2md

.. Registers the top-level package as a cross-reference target (it renders
   nothing): every module below is documented by its own `automodule`, but the
   package itself is only ever referred to, so without this the `:py:mod:`
   references to it dangle under `sphinx -n`.
.. py:module:: document2md

Version |document2md_version|. This package was extracted from the `LegalIA
<https://github.com/INGEOTEC/LegalIA>`_ monorepo at commit ``e1f258c``; the
packages it used to share a repository with are documented at
`legalia.readthedocs.io <https://legalia.readthedocs.io/en/latest/>`_.

:py:mod:`document2md` converts a PDF or a set of scanned page images — from
Mexico's official gazette (DOF, *Diario Oficial de la Federación*) or any
other document — into Markdown, optionally cropped down to a single note.
It has two backends: `mineru <https://github.com/opendatalab/MinerU>`_ (OCR
and layout analysis, for scanned pages) and
`pymupdf4llm <https://github.com/pymupdf/RAG>`_ (reading a born-digital
PDF's own embedded text layer, no OCR needed); :py:mod:`document2md`'s own
contribution is keeping mineru's ``mineru-api`` server warm across a batch
of documents, stitching several scanned pages of the same note into one
continuous Markdown document, rewriting mineru's raw HTML table fallback
into Markdown tables, and cropping the result down to a single note by
locating its title and the next note's title in the OCR'd text. It has no
notion of a "note"/legal provision of its own, and no download of its own —
getting a whole DOF edition's PDF by date and edition is
`dofjson.download_edicion_pdf
<https://github.com/INGEOTEC/LegalIA/tree/master/packages/dofjson>`_'s
job; `nota2md <https://github.com/INGEOTEC/LegalIA/tree/master/packages/nota2md>`_
is what calls into :py:mod:`document2md` at all, and only
as its OCR fallback for legal provisions predating the HTML era. Both live in
the `LegalIA <https://github.com/INGEOTEC/LegalIA>`_ repository and are not
dependencies of this one.

PyMuPDF and pymupdf4llm are AGPL-3.0 licensed, unlike the rest of
:py:mod:`document2md` (Apache-2.0); see the README's Install section.

document2md's architecture
==========================

Both entry points below — the ``document2md`` command line (:py:mod:`document2md.cli`)
and :py:class:`~document2md.batch.BatchConverter` (:py:mod:`document2md.batch`) used directly
from Python — go through the same pipeline. ``BatchConverter`` resolves which backend
converts the document (``mineru`` or ``pymupdf``; see below), starting
:py:class:`~document2md.mineru_server.MineruServer` to keep a single ``mineru-api``
process warm across a batch only for the ``mineru`` backend.
:py:mod:`document2md.converter` shells out to mineru and
:py:mod:`document2md.pymupdf_backend` reads a PDF's own embedded text layer;
:py:mod:`document2md.tables` rewrites mineru's raw HTML table fallback into
Markdown tables, and :py:mod:`document2md.cutter` optionally crops the result down
to one note by title, for either backend's output.

.. graphviz::
   :alt: document2md's conversion pipeline, from entry points to Markdown output.

   digraph document2md_flow {
       rankdir=LR;
       fontname="sans-serif";
       node [fontname="sans-serif", fontsize=11, shape=box, style="rounded,filled",
             fillcolor="#f4f4f4", color="#888888"];
       edge [fontname="sans-serif", fontsize=9, color="#888888"];

       cli [label="cli.py\n(document2md command)"];
       batch [label="batch.py\nBatchConverter"];
       server [label="mineru_server.py\nMineruServer"];
       mineru [label="mineru CLI\n(external OCR/layout)", style="rounded,dashed", fillcolor="#ffffff"];
       converter [label="converter.py\nconvert_to_markdown()\nconvert_images_to_markdown()"];
       pymupdf_backend [label="pymupdf_backend.py\nhas_text_layer()\nconvert_to_markdown()"];
       tables [label="tables.py\nhtml_tables_to_markdown()"];
       cutter [label="cutter.py\ncut_markdown_by_titles()\n(optional, if titulo given)"];
       output [label="Markdown output", shape=note, style=filled, fillcolor="#ffffff"];

       cli -> batch;
       batch -> server [label="__enter__ / __exit__ (mineru backend)"];
       server -> converter [label="MINERU_API_URL", style=dashed];
       batch -> converter [label="__call__ (mineru backend)"];
       batch -> pymupdf_backend [label="__call__ (pymupdf backend)"];
       converter -> mineru [label="subprocess"];
       converter -> tables [label="rewrite HTML tables"];
       tables -> batch [label="Markdown"];
       pymupdf_backend -> batch [label="Markdown"];
       batch -> cutter [label="titulo given"];
       cutter -> output;
       batch -> output [label="titulo omitted"];
   }

The sections below are ordered the way a conversion actually flows through
the package: the two entry points first, then each module in turn. Every
class and function is documented, including private/internal helpers
(leading-underscore names) — useful when extending or debugging the package,
though they are not part of its public API and can change without notice.

**The one documented exception to "every public symbol has a verified
example".** Entering :py:class:`~document2md.batch.BatchConverter`
starts a real ``mineru-api`` server, and calling it shells out to the real
``mineru`` CLI, or reads a PDF through the real ``pymupdf``/``pymupdf4llm`` —
none of which are installed in the doctest job on purpose
(``mineru[pipeline]`` and ``pymupdf4llm`` are both left out; keeping them out
is exactly why ``.readthedocs.yaml``/``test.yml`` install ``document2md`` with
``--no-deps``). Every example below that would actually invoke mineru or
pymupdf4llm is marked ``# doctest: +SKIP`` and is instead exercised for real
by ``tests/test_batch.py``, ``tests/test_cli.py`` and
``tests/test_pymupdf_backend.py``, which mock only the mineru/pymupdf
boundary (``document2md.converter.convert_to_markdown``/
``convert_images_to_markdown``, ``document2md.batch.MineruServer``,
``document2md.pymupdf_backend``) and run everything else — argument
forwarding, backend resolution, title cropping, ``keep_pages``,
``keep_mineru_output`` — for real. ``document2md.cutter`` below, needing
neither backend nor any file on disk, is genuinely executed.

``document2md.cli`` — command-line entry point
----------------------------------------------

The ``document2md`` console script. Parses arguments and drives one
:py:class:`~document2md.batch.BatchConverter` conversion, printing where the
result was saved:

.. code-block:: console

   $ document2md --pdf edicion.pdf --outdir output
   Converting to Markdown (mineru)...
   Markdown saved to: output/edicion.md

``--filename`` defaults to the ``--pdf`` file's own name (with a ``.md``
extension); it is required with ``--images``, since a list of scanned pages
has no single input name to derive one from:

.. code-block:: console

   $ document2md --images nota-200-p1.jpg nota-200-p2.jpg --filename nota-200.md --outdir output
   Converting to Markdown (mineru)...
   Markdown saved to: output/nota-200.md

``--backend {auto,mineru,pymupdf}`` (default ``auto``) selects the
conversion backend; ``auto`` resolves to ``mineru`` when the ``mineru`` CLI
is on ``PATH``, otherwise to ``pymupdf``, which reads a PDF's own embedded
text layer instead of running OCR — far faster, at the cost of slightly
worse structure, and unusable on scanned page images or a PDF without
enough of a text layer. In either of those cases (or if ``mineru`` is
explicitly requested but isn't installed), ``document2md`` exits with a
message pointing at ``pip install "document2md[mineru]"`` instead of a
traceback.

``--titulo``/``--titulo-siguiente`` crop the result to one note;
``--keep-pages`` also keeps the uncropped conversion alongside it, as
``<outdir>/<pdf stem>.full.md``:

.. code-block:: console

   $ document2md --pdf edicion.pdf --outdir output \
       --titulo "ACUERDO por el que se..." \
       --titulo-siguiente "DECRETO por el que se..." \
       --keep-pages
   Converting to Markdown (mineru)...
   Markdown saved to: output/edicion.md

.. automodule:: document2md.cli
   :members:
   :private-members:
   :undoc-members:

``document2md.batch`` — Python entry point
------------------------------------------

:py:class:`~document2md.batch.BatchConverter` is the package's public entry point when
used from Python, re-exported off :py:mod:`document2md` itself. As a context
manager it starts a persistent ``mineru-api`` server on ``__enter__``
(skipped if a caller further up already has one running via
``MINERU_API_URL`` — see ``document2md.mineru_server`` below) and stops it on
``__exit__``; calling it converts one document — a single PDF path, or a
list of image paths for a document spanning several scanned pages — to
Markdown:

>>> from document2md import BatchConverter
>>>
>>> jobs = [
...     ("a.pdf", "output", "a.md"),
...     (["b-p1.jpg", "b-p2.jpg"], "output", "b.md"),
... ]
>>> with BatchConverter() as convert:  # doctest: +SKIP
...     for path_or_paths, outdir, filename in jobs:
...         convert(path_or_paths, outdir, filename)

``backend`` (default ``"auto"``) selects who converts the document:
``"auto"``, ``"mineru"`` or ``"pymupdf"``; any other value raises
``ValueError``. ``"auto"`` resolves to ``"mineru"`` when the ``mineru`` CLI
is on ``PATH``, otherwise to ``"pymupdf"`` — mineru remains the reference
backend where it is installed, and the light backend only makes installing
it optional. Resolution, and the check that the resolved backend's own
dependency is installed, happen in ``__enter__``, before any document is
converted; the resolved name is then available as ``self.backend``. When
the resolved backend's dependency isn't installed, entering raises
``RuntimeError`` pointing at the right install command.

``"pymupdf"`` reads a PDF's own embedded text layer instead of running
OCR — far faster, at the cost of slightly worse structure. It has no use
for a list of page images (which always need OCR) or a PDF without enough
of a text layer (see :py:func:`~document2md.pymupdf_backend.has_text_layer`);
calling it on either raises ``RuntimeError`` pointing at
``pip install "document2md[mineru]"`` rather than silently falling back to
mineru. ``keep_mineru_output`` and ``timeout`` are accepted but ignored for
this backend, since it needs neither.

Passing ``titulo``/``titulo_siguiente`` crops the OCR'd Markdown down to the
text between the two titles, as they appear in the gazette's own index —
useful because a scanned edition page usually holds the tail of one note and
the head of the next. Title matching is fuzzy (OCR text rarely matches an
index title exactly), so ``min_confidence`` (default ``0.6``) sets how
confident a match has to be before it is trusted — a weaker one is treated as
not found and the crop falls back to keeping more text rather than dropping
content (see ``document2md.cutter`` below). ``keep_pages=True`` also keeps the
uncropped Markdown, as ``<outdir>/<pdf stem>.full.md``; ``keep_mineru_output=True``
keeps mineru's own raw output instead of discarding it (see
``document2md.converter`` below):

>>> with BatchConverter() as convert:  # doctest: +SKIP
...     convert(
...         "edicion.pdf", "output", "nota.md",
...         titulo="ACUERDO por el que se...",
...         titulo_siguiente="DECRETO por el que se...",
...         min_confidence=0.8,
...         keep_pages=True,
...         keep_mineru_output=True,
...     )

`nota2md.legal_provisions
<https://github.com/INGEOTEC/LegalIA/tree/master/packages/nota2md>`_
accepts an already-``__enter__``'d
:py:class:`~document2md.batch.BatchConverter` as its own ``converter`` parameter, so a
batch of DOF legal provisions can share the same warm server too — the way
to OCR many pre-HTML-era notes without paying mineru's startup cost once per
note (``nota2md`` lives in the `LegalIA
<https://github.com/INGEOTEC/LegalIA>`_ repository and is not a dependency of
this one, so this example is skipped here as well):

>>> import nota2md  # doctest: +SKIP
>>> codigos_sin_html = [4430696, 4430697]
>>> with BatchConverter() as ins:  # doctest: +SKIP
...     for cod_nota in codigos_sin_html:
...         nota2md.legal_provisions(cod_nota, "output", source="image", converter=ins)

.. automodule:: document2md.batch
   :members:
   :private-members:
   :undoc-members:

``document2md.mineru_server`` — keeping mineru-api warm
-------------------------------------------------------

``BatchConverter.__enter__`` starts a :py:class:`~document2md.mineru_server.MineruServer`,
which launches ``mineru-api`` as a subprocess, waits for it to report
healthy, and points every conversion in the batch at it via the
``MINERU_API_URL`` environment variable — instead of the ``mineru`` CLI
spinning up (and reloading all layout/OCR models into) a fresh temporary
server on every single invocation.

.. automodule:: document2md.mineru_server
   :members:
   :private-members:
   :undoc-members:

``document2md.converter`` — running mineru
------------------------------------------

Each ``BatchConverter.__call__`` shells out to the ``mineru`` CLI —
reusing the ``MINERU_API_URL`` server above when set — to OCR a PDF
(:py:func:`~document2md.converter.convert_to_markdown`) or one or more scanned
page images (:py:func:`~document2md.converter.convert_images_to_markdown`), then
hands mineru's raw Markdown to ``document2md.tables`` below before writing the
result to disk.

.. automodule:: document2md.converter
   :members:
   :private-members:
   :undoc-members:

``document2md.pymupdf_backend`` — reading a PDF's own text layer
------------------------------------------------------------------

For a born-digital PDF, ``BatchConverter.__call__`` can instead read the
PDF's own embedded text layer with `pymupdf4llm <https://github.com/pymupdf/RAG>`_
(:py:func:`~document2md.pymupdf_backend.convert_to_markdown`) — far faster than
OCR, at the cost of slightly worse structure, and with no image extraction.
:py:func:`~document2md.pymupdf_backend.has_text_layer` is what ``BatchConverter``
uses to decide whether a given PDF qualifies: at least ``MIN_TEXT_PAGE_FRACTION``
(``0.8``) of its pages must each have at least ``MIN_CHARS_PER_PAGE`` (``50``)
non-whitespace characters of extractable text, tolerating a few scanned
inserts in an otherwise digital document. PyMuPDF/pymupdf4llm aren't
installed in this doctest job (see the note above), so this example, which
builds a one-page PDF with PyMuPDF inline, is skipped here as well:

>>> import pymupdf  # doctest: +SKIP
>>> from document2md.pymupdf_backend import has_text_layer
>>> doc = pymupdf.open()  # doctest: +SKIP
>>> page = doc.new_page()  # doctest: +SKIP
>>> _ = page.insert_text((72, 72), "Born-digital text, not a scan.")  # doctest: +SKIP
>>> doc.save("a.pdf")  # doctest: +SKIP
>>> has_text_layer("a.pdf")  # doctest: +SKIP
True

.. automodule:: document2md.pymupdf_backend
   :members:
   :private-members:
   :undoc-members:

``document2md.tables`` — HTML tables to Markdown tables
-------------------------------------------------------

mineru renders simple tables as Markdown but falls back to raw HTML
(``<table>…</table>`` with rowspan/colspan) for anything complex; this
module rewrites those into GitHub Markdown tables so both conversion
functions above return Markdown all the way through.

.. automodule:: document2md.tables
   :members:
   :private-members:
   :undoc-members:

``document2md.cutter`` — cropping to a single note
--------------------------------------------------

When ``BatchConverter`` is called with ``titulo``, the last step before the
Markdown is written is slicing it down to the text between this note's title
and the next note's title, as they appear in the gazette's own per-day
index — the OCR'd text otherwise spans whatever notes shared that scanned
page. Needing neither mineru nor a file on disk, this is the one example on
this page that runs for real rather than under ``# doctest: +SKIP``:

>>> from document2md.cutter import cut_markdown_by_titles
>>> markdown = (
...     "resto de la nota anterior.\n\n"
...     "## Acuerdo de regularizacion de titulos\n\n"
...     "Cuerpo del acuerdo.\n\n"
...     "## Norma Oficial Mexicana NOM-042-NUCL\n\n"
...     "Nota siguiente, excluir.\n"
... )
>>> cut = cut_markdown_by_titles(
...     markdown,
...     "Acuerdo de regularizacion de titulos",
...     "Norma Oficial Mexicana NOM-042-NUCL",
... )
>>> print(cut)
## Acuerdo de regularizacion de titulos
<BLANKLINE>
Cuerpo del acuerdo.

.. automodule:: document2md.cutter
   :members:
   :private-members:
   :undoc-members:
