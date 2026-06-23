# axm-config

Non-sensitive runtime config under ~/.axm (env>file>default)

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-config/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-config/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-config/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Non-sensitive runtime config under ~/.axm (env>file>default)

## Features

- _TBD — describe the main features of this package here._

## Installation

```bash
uv add axm-config
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-config"]

[tool.uv.sources]
axm-config = { workspace = true }
```

## Development

This package is part of the **axm-draft-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-config

# From workspace root
make test-axm-config
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
