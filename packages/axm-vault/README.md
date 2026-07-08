# axm-vault

Catalog-resolver secrets manager (keyring + SecretStr) for AXM

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/coverage.json" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
</p>

---

## Overview

Catalog-resolver secrets manager (keyring + SecretStr) for AXM

## Features

- **Value-less catalog** — pydantic v2 models (`Sensitivity`, `CredentialSpec`, `CredentialGroup`) describe credential *schema* only; no field ever holds a secret value.
- **Entry-point discovery** — `load_catalog()` aggregates `axm.credentials` groups contributed by packages (empty-safe, cached).
- **Layered resolution** — `Resolver` walks `env > file > keyring > default > prompt`; the file tier is delegated to `axm-config`, the keyring tier is consulted only for `SECRET` specs.
- **Typed binding** — `bind(model, group)` builds a pydantic model from resolved values, wrapping `SECRET` fields as `SecretStr` and returning the concrete model type.
- **Value-free doctor** — `doctor_data()` / the `vault_doctor` tool report each credential's `{layer, present}` provenance without ever returning a secret.
- **MCP tools** — `vault_doctor` (provenance) and `vault_set` (keyring/config) ship as `axm.tools` (MCP + CLI + DAG node).
- **Operator CLI** — `axm-vault` exposes `setup`/`get`/`set`/`rotate`/`doctor`/`path`; interactive `setup` is TTY-guarded and idempotent, `get` masks secrets unless `--reveal`.
- **Frozen & strict** — immutable models that forbid unknown fields (`frozen=True`, `extra="forbid"`).

See the [documentation](https://axm-protocols.github.io/axm-forge-workspace/) for the full guide, including [how to declare your package's credentials](docs/howto/declare-credentials.md).

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

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) uv workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups

# Run tests for this package
uv run --package axm-vault --directory packages/axm-vault pytest -x -q

# Lint + type check + security audit + tests, all packages, from the root
make check
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
