Backends
========

:py:class:`~document2md.batch.BatchConverter` and the ``document2md`` CLI
share one selector: a ``backend`` argument (``--backend`` on the CLI)
naming who converts a given document — ``"auto"`` (default), ``"mineru"``
or ``"pymupdf"``. This page is about how that selector is implemented, and
what it takes to add a fourth backend; see the user site's
`Backends <https://ingeotec.github.io/document2md/pages/backends.html>`_
page for the `auto` policy and a comparison of the two backends that ship
today.

How resolution and dispatch work
---------------------------------

Three steps, in order:

1. **Validation, in** ``BatchConverter.__init__``. The requested name is
   checked against ``document2md.batch.BACKENDS``; anything else
   raises ``ValueError`` immediately, before any I/O happens.
2. **Resolution, in** ``BatchConverter.__enter__``. ``"auto"`` becomes
   ``"mineru"`` when ``shutil.which("mineru")`` finds it on ``PATH``,
   otherwise ``"pymupdf"``; any other requested name passes through
   unchanged. The resolved name is stored as ``self.backend``. Still in
   ``__enter__``, the resolved backend's own dependency is checked (each
   backend's ``_require_*`` function — see below) and, only for
   ``mineru``, a :py:class:`~document2md.mineru_server.MineruServer` is
   started. Doing this in ``__enter__`` rather than lazily on the first
   call means a missing dependency is reported before any document is
   converted, not partway through a batch.
3. **Dispatch, in** ``BatchConverter.__call__``. A plain ``if``/``elif`` on
   ``self.backend`` routes to the right converter function. The
   ``pymupdf`` branch additionally rejects input it structurally cannot
   handle — a list of page images, or a PDF that fails
   :py:func:`~document2md.pymupdf_backend.has_text_layer` — by raising
   ``RuntimeError`` rather than silently falling back to ``mineru``.

The contract a backend must satisfy
-------------------------------------

Concretely, from ``mineru``/``pymupdf`` as the two examples:

- **A conversion function** taking an input path (or list of paths, for
  ``mineru``'s scanned-page-image case) and a ``md_path``, writing
  Markdown to ``md_path`` and returning nothing —
  :py:func:`document2md.converter.convert_to_markdown` and
  :py:func:`document2md.pymupdf_backend.convert_to_markdown`.
- **A** ``_require_*()`` **function** raising ``RuntimeError`` with an
  install hint when the backend's own dependency isn't available —
  :py:func:`document2md.converter._require_mineru` and
  :py:func:`document2md.pymupdf_backend._require_pymupdf`. ``BatchConverter.__enter__``
  calls the right one for the resolved backend.
- **Lazy imports of the backend's own dependency**, inside functions
  rather than at module level. The docs build installs the package
  ``--no-deps`` (see :doc:`development`), and autodoc must still be able
  to import every module even when a backend's dependency isn't
  installed at all.

Adding a backend
-----------------

1. Write the new module (``document2md/<name>_backend.py`` is the
   existing naming pattern, though not enforced), with a conversion
   function and a ``_require_*()`` function satisfying the contract
   above. Import the backend's own dependency lazily, inside functions.
2. Add the new name to ``document2md.batch.BACKENDS``.
3. Extend ``BatchConverter.__enter__``'s resolution: decide what ``"auto"``
   should do when this backend is also available (mineru is preferred
   over pymupdf today — see the user site's Backends page for why), call
   the new ``_require_*()`` for the resolved backend, and start any
   server the backend needs (most won't).
4. Extend ``BatchConverter.__call__``'s dispatch with a new branch, and
   decide what it does with input it can't handle — raising
   ``RuntimeError`` naming what to install or use instead, as ``pymupdf``
   does, rather than silently falling back to another backend.
5. Add the new choice to the CLI's ``--backend`` ``choices``.
6. Tests: backend validation and resolution in ``tests/test_batch.py``
   (following the existing ``mineru``/``pymupdf`` cases), CLI parsing and
   the progress-line/error-message wiring in ``tests/test_cli.py``, and a
   dedicated test module for the backend's own conversion function and
   ``_require_*()`` check, run for real rather than mocked if the
   dependency is small enough to install directly (as
   ``tests/test_pymupdf_backend.py`` does).
7. Document it: a one-sentence :doc:`api/index` entry and API page, this
   page's contract/dispatch description if the new backend needs
   anything beyond it, and the user site's Backends and Install pages.
