# axm-ingot

Canonical shared helpers factored out of duplicated AXM code.

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge-workspace/gh-pages/badges/axm-ingot/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Canonical shared helpers factored out of duplicated AXM code.

## Features

- _TBD — describe the main features of this package here._

## Installation

```bash
uv add axm-ingot
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-ingot"]

[tool.uv.sources]
axm-ingot = { workspace = true }
```

## Development

This package is part of the **axm-forge-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-ingot

# From workspace root
make test-axm-ingot
```

## License

MIT — © 2026 AXM Protocols
