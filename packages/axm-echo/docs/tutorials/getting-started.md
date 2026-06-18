# Getting Started

This tutorial walks you through installing `axm-echo` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-echo
```

Or with pip:

```bash
pip install axm-echo
```

To enable the optional neural backend (`torch` + `sentence-transformers`):

```bash
uv add "axm-echo[neural]"   # or: pip install "axm-echo[neural]"
```

## Step 1: Embed a Few Texts

The `tfidf` backend is pure-CPU (numpy + scikit-learn) and never imports
torch, so it works out of the box on a base install:

```python
from axm_echo import embed, neighbors

texts = [
    "raise an error when the API rate limit is exceeded",
    "raise an error when the request quota is exceeded",
    "read rows from a CSV file into a list of dicts",
]
matrix = embed(texts, backend="tfidf")

# Nearest neighbours of the first text (exact cosine top-k).
for idx, score in neighbors(matrix[0], matrix, k=2):
    print(f"{score:.3f}  {texts[idx]}")
```

## Step 2: Extract a Corpus From Code

`extract_package` walks a package via [axm-ast](https://pypi.org/project/axm-ast/)
and returns one record per public function/class:

```python
from pathlib import Path

from axm_echo import extract_package

for sym in extract_package(Path("packages/axm-echo")):
    print(sym["qualname"], "->", sym["doc_first_line"])
```

Only first-party source is extracted: the walk skips test trees and any
vendored or generated subtree (a committed `.venv`, `site-packages`,
`__pycache__`, `node_modules`, `.tox`, `build`, `dist`, `.git`), so
third-party libraries installed inside a checked-in virtualenv never leak
into the corpus.

`extract_monorepo()` does the same across every package declared in
`~/.axm/echo.toml` (`workspace_roots`), degrading gracefully to the
current directory when no config is present. Each listed root is treated
as a workspace, so packages are discovered at `<root>/packages/<pkg>` (the
monorepo convention) as well as in the flat `other/<pkg>` layout. A
directory only counts as a package when it carries a real marker — a
`src/` directory or a `pyproject.toml` — so doc folders such as
`docs/gen_ref_pages.py` are never mistaken for packages.

## Step 3: Run the Tests

```bash
cd packages/axm-echo
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [Architecture](../explanation/architecture.md) — How the project is structured
