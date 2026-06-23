# axm-vault

Catalog-resolver secrets manager (keyring + SecretStr) for AXM

<p align="center">
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-vault/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-vault/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-systems/axm-draft-workspace/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-systems/axm-draft-workspace/gh-pages/badges/axm-vault/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Catalog-resolver secrets manager (keyring + SecretStr) for AXM

## Features

- **Value-less catalog** — pydantic v2 models (`Sensitivity`, `CredentialSpec`, `CredentialGroup`) describe credential *schema* only; no field ever holds a secret value.
- **Frozen & strict** — immutable models that forbid unknown fields (`frozen=True`, `extra="forbid"`).

## Installation

```bash
uv add axm-vault
```

Or as a workspace dependency in `pyproject.toml`:

```toml
[project]
dependencies = ["axm-vault"]

[tool.uv.sources]
axm-vault = { workspace = true }
```

## Development

This package is part of the **axm-draft-workspace** uv workspace.

```bash
# Run tests for this package
uv run pytest --package axm-vault

# From workspace root
make test-axm-vault
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
