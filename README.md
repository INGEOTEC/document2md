# document2md

[![test](https://github.com/INGEOTEC/document2md/actions/workflows/test.yml/badge.svg)](https://github.com/INGEOTEC/document2md/actions/workflows/test.yml)
[![Documentation Status](https://readthedocs.org/projects/document2md/badge/?version=latest)](https://document2md.readthedocs.io/en/latest/)

Converts a PDF, or a set of scanned page images, into Markdown — any
document, such as an edition of Mexico's official gazette (DOF, *Diario
Oficial de la Federación*) — optionally cropped down to a single note.
It's a wrapper
around [mineru](https://github.com/opendatalab/MinerU) for the OCR/layout
analysis itself; `document2md`'s own contribution is:

- Keeping mineru's `mineru-api` server warm across a batch of documents,
  instead of paying its startup (and model-loading) cost once per document.
- Stitching the OCR of a list of page images (several scanned pages of the
  same note) into one continuous Markdown document.
- Rewriting the raw HTML tables mineru falls back to (rowspan/colspan) into
  Markdown tables, so the output is Markdown all the way through.
- Cropping the result down to a single note, by locating its title and the
  next note's title in the OCR'd text — useful because a scanned page
  usually holds the tail of one note and the head of the next.

It was extracted from the [LegalIA](https://github.com/INGEOTEC/LegalIA)
monorepo at commit `e1f258c`, where every commit of its earlier history (as
`packages/document2md`, and as `packages/dof2md` before the rename) can still
be read.

## Install

```bash
pip install document2md
```

installs the package with no OCR backend — `document2md`'s own contribution
(server lifecycle, page stitching, table rewriting, title cropping) with
none of them wired to a converter yet. To convert anything, add the
`mineru` backend:

```bash
pip install "document2md[mineru]"
```

This is the only backend available today; `--backend`/`BatchConverter(backend=...)`
name it explicitly so a lighter backend can be added later without a
default changing under anyone. `nota2md`'s `ocr` extra (in the LegalIA
repository) must depend on `document2md[mineru]>=0.4.0`, not a bare
`document2md>=0.3.0`, or `pip install nota2md[ocr]` stops installing mineru.

For development, from a clone of this repository:

```bash
pip install -e ".[mineru,test]"
```

## Usage

### CLI

`document2md` takes exactly one input source — a local PDF or a set of local page
images — and converts it to Markdown. It never downloads anything itself;
get the PDF first (e.g. `dofjson.download_edicion_pdf` for a whole DOF
edition by date and edition, see the
[dofjson README](https://github.com/INGEOTEC/LegalIA/tree/master/packages/dofjson)),
then convert it:

```bash
document2md --pdf edicion.pdf   # a local PDF

document2md --images pagina-1.jpg pagina-2.jpg \
    --filename out.md      # scanned pages, in order
```

`--filename` sets the output Markdown's name; with `--pdf` it defaults to
the PDF's own name (`edicion.pdf` → `edicion.md`), but with `--images` it's
required, since a set of images has no single name to derive one from.
`--outdir` sets the output directory (default: `output/`).

Since one edition's PDF holds every note published that day,
`--titulo`/`--titulo-siguiente` crop the resulting Markdown down to just one
note — its own title, and the next note's title, as they appear in the
gazette's own index:

```bash
document2md --pdf edicion.pdf \
    --titulo "ACUERDO por el que se..." \
    --titulo-siguiente "DECRETO por el que se..."
```

Title matching is fuzzy (OCR text rarely matches an index title exactly), so
a match below `--min-confidence` (default `0.6`) is treated as not found and
the crop falls back to keeping more text rather than dropping content. Other
flags:

- `--keep-pages` — also keep the uncropped Markdown, as
  `<outdir>/<pdf stem>.full.md`.
- `--keep-mineru-output` — keep mineru's own raw output (layout/model JSON,
  rendered PDFs...) in `<outdir>/<pdf stem>_mineru/` instead of discarding
  it; useful when a conversion looks wrong and mineru's own read of the page
  is the first thing worth inspecting.
- `--backend {auto,mineru}` (default `auto`) — which backend converts the
  document; `auto` currently always resolves to `mineru`, the only backend
  available today. If the `mineru` extra isn't installed, `document2md` exits
  with a message telling you to `pip install "document2md[mineru]"` instead
  of a traceback.

### Python: batch conversion

Converting many documents in one run is where mineru's startup cost starts
to matter. `BatchConverter` keeps a single `mineru-api` server warm across
the whole batch instead of restarting it per document:

```python
from document2md import BatchConverter

jobs = [
    ("a.pdf", "output", "a.md"),
    (["b-p1.jpg", "b-p2.jpg"], "output", "b.md"),
]

with BatchConverter() as convert:
    for path_or_paths, outdir, filename in jobs:
        convert(path_or_paths, outdir, filename)
```

Each call takes a single PDF path, or a list of image paths for a document
spanning several scanned pages, and writes the result to `outdir/filename`.
The same `titulo`/`titulo_siguiente`, `min_confidence`, `keep_pages` and
`keep_mineru_output` options the CLI exposes are also its keyword
arguments — see `BatchConverter.__call__`'s docstring for the full
signature. `BatchConverter(backend="auto")` (the default) picks which
backend does the conversion — `"mineru"`, the only one available today, is
what `"auto"` resolves to; the resolved name is available as
`convert.backend` once entered.

`nota2md.legal_provisions` accepts an already-`__enter__`'d `BatchConverter`
as its own `converter` parameter, so a batch of DOF legal provisions can
share the same warm server too.

## Tests

```bash
pytest tests
pytest dof2md/tests
```
