Architecture
============

Both entry points — the ``document2md`` command line
(:py:mod:`document2md.cli`) and :py:class:`~document2md.batch.BatchConverter`
(:py:mod:`document2md.batch`) used directly from Python — go through the
same pipeline. ``BatchConverter`` resolves which backend converts a given
document (``mineru`` or ``pymupdf``; see :doc:`backends`), starting
:py:class:`~document2md.mineru_server.MineruServer` to keep a single
``mineru-api`` process warm across a batch only for the ``mineru`` backend.
:py:mod:`document2md.converter` shells out to mineru and
:py:mod:`document2md.pymupdf_backend` reads a PDF's own embedded text
layer; :py:mod:`document2md.tables` rewrites mineru's raw HTML table
fallback into Markdown tables, and :py:mod:`document2md.cutter` optionally
crops the result down to one section by title, for either backend's
output.

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

The sections below walk the pipeline in the order a conversion actually
flows through it.

``document2md.cli`` — command-line entry point
------------------------------------------------

The ``document2md`` console script. Parses arguments and drives one
:py:class:`~document2md.batch.BatchConverter` conversion, printing the
resolved backend and where the result was saved. See the user site's
`Command line <https://ingeotec.github.io/document2md/pages/cli.html>`_
page for its flags and worked examples; :doc:`api/cli` for the full API
reference.

``document2md.batch`` — Python entry point
---------------------------------------------

:py:class:`~document2md.batch.BatchConverter` is the package's public entry
point when used from Python, re-exported off :py:mod:`document2md` itself.
As a context manager, entering it resolves the requested backend and
starts a persistent ``mineru-api`` server only when that backend is
``mineru`` (skipped if a caller further up already has one running via
``MINERU_API_URL`` — see ``document2md.mineru_server`` below); exiting
stops it. Calling it converts one document — a single PDF path, or a list
of image paths for a document spanning several scanned pages — to
Markdown. See :doc:`backends` for how resolution and dispatch work, and
the user site's `Python <https://ingeotec.github.io/document2md/pages/python.html>`_
page for worked examples; :doc:`api/batch` for the full API reference.

``document2md.mineru_server`` — keeping mineru-api warm
-----------------------------------------------------------

``BatchConverter.__enter__`` starts a
:py:class:`~document2md.mineru_server.MineruServer`, which launches
``mineru-api`` as a subprocess, waits for it to report healthy, and points
every conversion in the batch at it via the ``MINERU_API_URL`` environment
variable — instead of the ``mineru`` CLI spinning up (and reloading all
layout/OCR models into) a fresh temporary server on every single
invocation. See :doc:`api/mineru_server` for the full API reference.

``document2md.converter`` — running mineru
-----------------------------------------------

Each ``BatchConverter.__call__``, under the ``mineru`` backend, shells out
to the ``mineru`` CLI — reusing the ``MINERU_API_URL`` server above when
set — to OCR a PDF (:py:func:`~document2md.converter.convert_to_markdown`)
or one or more scanned page images
(:py:func:`~document2md.converter.convert_images_to_markdown`), then hands
mineru's raw Markdown to ``document2md.tables`` below before writing the
result to disk. See :doc:`api/converter` for the full API reference.

``document2md.pymupdf_backend`` — reading a PDF's own text layer
----------------------------------------------------------------------

Under the ``pymupdf`` backend, ``BatchConverter.__call__`` instead reads a
born-digital PDF's own embedded text layer with
`pymupdf4llm <https://github.com/pymupdf/RAG>`_
(:py:func:`~document2md.pymupdf_backend.convert_to_markdown`) — far faster
than OCR, at the cost of slightly worse structure, and with no image
extraction. See :doc:`backends` for how a PDF qualifies for this backend
and :doc:`api/pymupdf_backend` for the full API reference.

``document2md.tables`` — HTML tables to Markdown tables
------------------------------------------------------------

mineru renders simple tables as Markdown but falls back to raw HTML
(``<table>…</table>`` with rowspan/colspan) for anything complex; this
module rewrites those into GitHub Markdown tables so the ``mineru``
backend's output is Markdown all the way through. See :doc:`api/tables`
for the full API reference.

``document2md.cutter`` — cropping to a single section
------------------------------------------------------------

When ``BatchConverter`` is called with ``titulo``, the last step before
the Markdown is written is slicing it down to the text between this
section's title and the next section's title, as they appear in the
source document's own index — the converted text otherwise spans whatever
sections shared a page. Needing no file on disk, this is a real,
executed example rather than one marked ``# doctest: +SKIP``:

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

See :doc:`api/cutter` for the full API reference.
