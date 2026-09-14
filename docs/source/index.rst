:mod:`document2md`
==================

.. image:: https://github.com/INGEOTEC/document2md/actions/workflows/test.yml/badge.svg
        :target: https://github.com/INGEOTEC/document2md/actions/workflows/test.yml

.. image:: https://badge.fury.io/py/document2md.svg
        :target: https://badge.fury.io/py/document2md

.. image:: https://readthedocs.org/projects/document2md/badge/?version=latest
        :target: https://document2md.readthedocs.io/en/latest/

.. Registers the top-level package as a cross-reference target (it renders
   nothing): every module below is documented by its own `automodule`, but the
   package itself is only ever referred to, so without this the `:py:mod:`
   references to it dangle under `sphinx -n`.
.. py:module:: document2md

Version |document2md_version|. :py:mod:`document2md` converts a PDF, or an
ordered set of scanned page images, into Markdown, via one of two backends
— `mineru <https://github.com/opendatalab/MinerU>`_ (OCR and layout
analysis) or `pymupdf4llm <https://github.com/pymupdf/RAG>`_ (reading a
born-digital PDF's own embedded text layer, no OCR needed) — optionally
cropped down to a single section. This package was extracted from the
`LegalIA <https://github.com/INGEOTEC/LegalIA>`_ monorepo at commit
``e1f258c``; the packages it used to share a repository with are
documented at `legalia.readthedocs.io <https://legalia.readthedocs.io/en/latest/>`_.

.. note::
   This is the **developer** documentation: architecture, backends, and
   the full API reference, for extending the package itself. If you only
   want to *use* document2md — install it, run it from the command line or
   from Python, pick a backend — see the user site at
   `ingeotec.github.io/document2md <https://ingeotec.github.io/document2md/>`_.

How this documentation is organised
====================================

.. toctree::
   :maxdepth: 2

   architecture
   backends
   development
   api/index

:doc:`architecture` walks through the conversion pipeline end to end, module
by module, in the order a document actually flows through it.
:doc:`backends` explains how backend resolution and dispatch work, and how
to add a new backend. :doc:`development` covers the repository's own
conventions — tests, docs and website builds, versioning, publishing.
:doc:`api/index` is the full API reference, one page per module, including
private/internal helpers — useful when extending or debugging the package,
though they are not part of its public API and can change without notice.
