# axm-echo

Similarity & echo detection over code corpora (numpy/scikit-learn).

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Similarity & echo detection over code corpora (numpy/scikit-learn).

## Features

- **Light base install** — pure numeric stack (`numpy`, `scikit-learn`) for
  classical similarity over code corpora; no heavyweight ML dependency.
- **Optional `[neural]` extra** — opt into `torch` + `sentence-transformers`
  only when neural embeddings are needed; `torch` is never resolved by the
  base install.
- Built on `axm-ast` for code-corpus extraction (consumed in later phases).

## Installation

```bash
# Base install — numpy + scikit-learn only (no torch)
uv add axm-echo

# With the neural backend — pulls torch + sentence-transformers
uv add "axm-echo[neural]"
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-echo"]

[tool.uv.sources]
axm-echo = { workspace = true }
```

## Development

This package is part of the **axm-forge-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-echo

# From workspace root
make test-axm-echo
```

## License

MIT — © 2026 Gabriel Jarry
