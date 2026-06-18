# axm-echo

Neural similarity & echo detection over code corpora (MiniLM + scikit-learn).

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-echo/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Neural similarity & echo detection over code corpora (MiniLM + scikit-learn).

## Features

- **Neural by default** — the `st` (MiniLM) backend ships in the base install
  (`torch` + `sentence-transformers`) and runs in-process; no extra to enable.
- **`tfidf` opt-out** — the pure-CPU `numpy` + `scikit-learn` backend stays
  available (`--backend tfidf`) for callers that want to avoid loading torch.
- Built on `axm-ast` for code-corpus extraction (consumed in later phases).

## Installation

```bash
# echo is neural by default — the install ships torch + sentence-transformers.
uv add axm-echo
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
