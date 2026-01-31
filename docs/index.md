# AXM

**Axiom eXtensible Manager** — The deterministic CLI for Python project governance.

![AXM Demo](assets/quickstart.gif)

## Features

- 🚀 **`axm init`** — Bootstrap production-grade Python projects
- 🔍 **`axm check`** — Verify project compliance with standards
- 📊 **`axm audit`** — Full project audit with quality grade (A-F)
- 📦 **`axm reserve`** — Reserve a package name on PyPI
- 🔄 **`axm version`** — Show AXM version

## Quick Start

```bash
pip install axm
axm init my-project
cd my-project
axm audit
```

## What AXM Checks

AXM enforces Python 2026 engineering standards across 4 categories:

| Category | Rules |
|----------|-------|
| Structure | pyproject.toml, README.md, src/, tests/ |
| Quality | Lint (ruff), Types (mypy), Complexity (radon) |
| Architecture | Circular imports, God classes, Coupling |
| Practice | Docstrings, Bare except, Security patterns |

## Next Steps

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [CLI Reference](reference/cli.md)
