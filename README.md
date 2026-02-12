# axm-ast

**Abstract Syntax Tree utilities for AXM Audit**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-ast/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/axm-init.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-ast/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-ast/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-ast?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-ast/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-ast/"><img src="https://img.shields.io/pypi/v/axm-ast" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-ast/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- ✅ **Modern Python** — 3.12+ with strict typing
- ✅ **Fast** — Optimized for performance
- ✅ **Tested** — Full coverage with pytest

## Installation

```bash
uv add axm-ast
```

## Quick Start

```python
from axm_ast import hello

print(hello())
```

## CLI Commands

| Command | Description |
|---|---|
| `make install` | Install all dependencies (dev + docs) |
| `make check` | Run lint + audit + test in one step |
| `make lint` | Lint with ruff |
| `make format` | Format with ruff |
| `make test` | Run pytest |
| `make audit` | Run pip-audit |
| `make docs-serve` | Preview docs locally |
| `make clean` | Remove build artifacts |

## Development

```bash
git clone https://github.com/axm-protocols/axm-ast.git
cd axm-ast
uv sync --all-groups
make check
```

## License

Apache-2.0 — © 2026 axm-protocols
