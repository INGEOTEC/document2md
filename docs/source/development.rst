Development
===========

This page condenses the repository's own ``CLAUDE.md``; that file is the
source of truth if the two ever disagree.

Repository layout
-------------------

The repository *is* the ``document2md`` package: ``pyproject.toml`` and
``document2md/`` sit at the root, alongside ``tests/`` for its pytest
suite. Two other things share the repository:

- ``dof2md/`` — a code-less final release for the package's old PyPI name,
  a *tombstone* (see below), with its own ``tests/``.
- ``website/`` — the Quarto user site published to GitHub Pages at
  `ingeotec.github.io/document2md <https://ingeotec.github.io/document2md/>`_;
  ``docs/`` is this Read the Docs developer site instead. The two have no
  overlapping page: Pages is for using the package, Read the Docs for
  extending it.

Two packages are published from one repository, so the release tag
convention is ``<pkg>-v<version>`` (``document2md-v0.4.0``,
``dof2md-v0.3.0``) rather than a bare ``v*``, which wouldn't say which one.

Running the tests
--------------------

.. code-block:: bash

   python -m pytest tests            # document2md
   python -m pytest dof2md/tests     # the tombstone

**Always two invocations, never a bare** ``pytest`` **at the repository
root.** Both suites live in a directory called ``tests``, and, more to the
point, the ``dof2md/`` container directory shadows the installed
``dof2md`` distribution as a namespace package at the repository root — so
a bare ``pytest`` would import the namespace-package ``dof2md`` silently
instead of raising, and ``dof2md/tests/test_tombstone.py`` would fail.
Pointing pytest at ``dof2md/tests`` puts ``dof2md/`` itself at the front of
``sys.path``, where the real raising module wins. ``test.yml`` runs them as
two separate jobs for the same reason.

The suite never imports ``mineru`` — it mocks the subprocess boundary
(``document2md.converter.convert_to_markdown``/``convert_images_to_markdown``,
``document2md.batch.MineruServer``) — so a light local install
(``pip install --no-deps -e .`` plus ``requests``, ``pymupdf4llm`` and
``pytest``) runs the whole suite without the gigabytes of
``mineru[pipeline]``. ``tests/test_pymupdf_backend.py`` is the one
exception: it exercises the real ``pymupdf``/``pymupdf4llm``, building its
own PDFs on the fly with PyMuPDF, since that backend is small and core
rather than optional.

Building the docs and the website
------------------------------------

.. code-block:: bash

   python -m sphinx -n -W --keep-going -b html docs/source docs/build/html
   python -m sphinx -b doctest docs/source docs/build/doctest
   quarto render website

The Sphinx HTML build is strict (``-n -W``): any broken cross-reference or
other warning fails it. The doctest build runs this site's few real,
executed examples (see :doc:`architecture`'s ``cutter`` example); usage
examples that would need ``mineru`` or ``pymupdf4llm`` live on the Pages
site instead, not here, so there is little left to mark
``# doctest: +SKIP``. Quarto (pinned at 1.9.38, matching
``.github/workflows/website.yml``) needs no Python, R or Jupyter to render
``website/``, since none of its pages execute code.

Versioning and publishing
----------------------------

``scripts/check_package_versions.py`` gates every pull request: a
package's ``__version__`` may be at most one release ahead of what's
published on PyPI (the next patch, or the next minor with patch reset to
0) — never equal, never further ahead. Publishing itself is a human
action: push a ``document2md-v<version>`` (or ``dof2md-v<version>``) tag
once ``__version__`` is bumped, with the ``TWINE`` secret set on the
repository; ``publish-pypi.yml`` refuses a tag that disagrees with
``pyproject.toml``. ``document2md`` must reach PyPI before or at the same
time as any ``nota2md`` release whose ``ocr`` extra requires it
(``document2md[mineru]>=0.4.0``), or ``pip install nota2md[ocr]`` breaks
for everyone outside the LegalIA repository. The Pages site publishes
itself, via ``website.yml``, on every push to ``main`` that touches
``website/``; Read the Docs must be imported once, by a human, at
readthedocs.org — nothing in the repository can do that.

The ``dof2md`` tombstone
---------------------------

``dof2md/`` is a code-less final release for the old PyPI name:
``__version__ = "0.3.0"``, then an unconditional ``ImportError`` naming
``document2md`` and ``pip install document2md``. Three rules, each guarded
by a test:

- ``__version__`` stays above the ``raise``, as a plain literal, so both
  setuptools' ``attr:`` resolution and ``check_package_versions.py`` can
  read it statically (AST, no import).
- It does not depend on ``document2md`` — a working shim would keep the
  old package alive as real, maintained code.
- ``[tool.document2md] tombstone = true`` in ``dof2md/pyproject.toml``
  exempts it from the one-step-ahead rule once its final version is
  published, since local and PyPI then agree forever.

Language policy
-------------------

Everything written into the repository is in English — identifiers,
comments, docstrings, commit messages, documentation, both sites included.
The one deliberate exception is the CLI's Spanish flags
``--titulo``/``--titulo-siguiente``, kept through the package's rename
because changing them would be a behaviour change, not a cleanup.
