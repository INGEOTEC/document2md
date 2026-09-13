# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this is

`document2md` converts a PDF, or an ordered set of scanned page images, into
Markdown, via OCR and layout analysis. It is a wrapper around
[mineru](https://github.com/opendatalab/MinerU); its own contribution is:

- keeping mineru's `mineru-api` server warm across a batch of documents
  (`BatchConverter`), instead of paying its startup and model-loading cost
  once per document;
- stitching the OCR of several page images of the same document into one
  continuous Markdown document;
- rewriting the raw HTML tables mineru falls back to (rowspan/colspan) into
  Markdown tables, so the output is Markdown all the way through;
- cropping the result down to one section, by locating its title and the next
  one's title in the OCR'd text (`cutter`) — a scanned page usually holds the
  tail of one document and the head of the next.

It was extracted from the [LegalIA](https://github.com/INGEOTEC/LegalIA)
monorepo at commit `e1f258c` (issue
[#233](https://github.com/INGEOTEC/LegalIA/issues/233)), where its whole
earlier history is still readable — as `packages/document2md`, and as
`packages/dof2md` before the rename.

## What this is *not*

- **It has no notion of a "note", a legal provision or the DOF.** It never had
  one after LegalIA's issue #134 moved the edition download out into
  `dofjson.download_edicion_pdf`, and that is exactly why it was renamed from
  `dof2md` to `document2md` (LegalIA's issue #228): *a package is named after
  what it does, not after the corpus that first needed it.*
- **It downloads nothing.** It only ever converts a PDF or images already on
  disk. Getting a document is the caller's problem.
- **The backend seam exists, with one backend behind it.** `BatchConverter(backend=...)`
  and the CLI's `--backend` accept `auto` (default) and `mineru`; `auto`
  resolves to `mineru`, the only backend implemented so far, and `mineru`
  itself is the `document2md[mineru]` extra rather than a hard dependency. A
  lightweight backend reading a PDF's own embedded text layer, for
  born-digital documents that need no OCR at all, is the follow-up issue that
  seam was built for.

## Layout

```
pyproject.toml            document2md itself; the repository *is* the package
setup.py                  two-line setuptools shim
document2md/              the package: cli, batch, mineru_server, converter,
                          tables, cutter
tests/                    its pytest suite
dof2md/                   the old PyPI name's tombstone (see below)
scripts/check_package_versions.py
docs/                     Sphinx site, published at document2md.readthedocs.io
.github/workflows/        test.yml, publish-pypi.yml
```

Two packages are published from this repository, so the release tag convention
is `<pkg>-v<version>` (`document2md-v0.3.0`, `dof2md-v0.3.0`) rather than a
bare `v*`, which would not say which one.

## The `dof2md` tombstone

`dof2md/` is a code-less final release for the old PyPI name: `__version__ =
"0.3.0"`, then an unconditional `ImportError` naming `document2md` and
`pip install document2md`. Three rules, each of which a test guards:

- **`__version__` stays above the `raise`, as a plain literal.** Both
  setuptools' `attr:` resolution and `scripts/check_package_versions.py`'s
  `local_version()` read it statically (AST, no import) — that is what makes a
  module which raises on import buildable and publishable at all.
  `dof2md/tests/test_tombstone.py` guards the ordering.
- **It does not depend on `document2md`.** A working shim was rejected: it
  would keep the old package alive as real, maintained code, and would let
  `pip install dof2md` quietly keep working through a transitive import.
- **`[tool.document2md] tombstone = true`** in `dof2md/pyproject.toml` exempts
  it from `check_package_versions.py`'s one-step-ahead rule: once
  `dof2md-v0.3.0` is published, local and PyPI agree forever, which the gate
  would otherwise report as a failure on every pull request from then on. The
  marker is data in the package it describes, so the next rename costs a key,
  not a code edit.

## Commands

```bash
pytest tests            # document2md
pytest dof2md/tests     # the tombstone
python scripts/check_package_versions.py
python -m sphinx -b doctest docs/source docs/build/doctest
python -m sphinx -b html docs/source docs/build/html
```

**The two pytest runs are two invocations on purpose, never a bare `pytest`.**
Both suites live in a directory called `tests`, and, more to the point, at the
repository root the `dof2md/` container directory shadows the installed
`dof2md` distribution as a namespace package — so `import dof2md` would
succeed, silently, instead of raising, and `test_tombstone.py` would fail.
Pointing pytest at `dof2md/tests` (which is a package, hence the empty
`__init__.py`) puts `dof2md/` itself at the front of `sys.path`, where the real
raising module wins. `test.yml` runs them as two matrix jobs for the same
reason.

The tests never import `mineru` — they mock the subprocess boundary
(`document2md.converter.convert_to_markdown` /
`convert_images_to_markdown`, `document2md.batch.MineruServer`) — so a local
install with `pip install --no-deps -e .` plus `requests` and `pytest` runs
the whole suite without the gigabytes of `mineru[pipeline]`. CI installs the
package fully (`pip install -e ".[test]"`, plus `libgl1`/`libglib2.0-0` for
mineru's opencv) on every supported Python, which is what proves the declared
dependency actually installs.

The docs' OCR examples are the one documented exception to "every public
symbol has a verified example": entering a `BatchConverter` starts a real
`mineru-api` server, so they are marked `# doctest: +SKIP` and verified
instead by `tests/test_batch.py` and `tests/test_cli.py`. The exception is
written on the docs page itself, not silently skipped.

## Publishing

Publishing is a human action: push a `document2md-v<version>` (or
`dof2md-v<version>`) tag once `__version__` is bumped, with the `TWINE` secret
set on this repository. `publish-pypi.yml` refuses a tag that disagrees with
`pyproject.toml`.

**`document2md` must reach PyPI before or at the same time as any `nota2md`
release whose `ocr` extra requires it** (`document2md>=0.3.0`), or
`pip install nota2md[ocr]` breaks for everyone outside the LegalIA repository.

## Language policy

Everything written into this repository is in English: identifiers, comments,
docstrings, commit messages, documentation. The one deliberate exception is
the CLI's Spanish flags `--titulo`/`--titulo-siguiente`, kept untouched
through the rename because changing them is a behaviour change, not a
cleanup.
