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

- **Value-less catalog** — pydantic v2 models (`Sensitivity`, `CredentialSpec`, `CredentialGroup`) describe credential *schema* only; defaults and descriptions must contain no real secrets (this is a provider responsibility).
- **Entry-point discovery** — `load_catalog()` aggregates `axm.credentials` groups contributed by packages (empty-safe, cached).
- **Layered resolution** — `Resolver` walks `env > file > keyring > default > prompt`; the file tier is delegated to `axm-config`, the keyring tier is consulted only for `SECRET` specs.
- **Typed binding** — `bind(model, group)` builds a pydantic model from resolved values, wrapping `SECRET` fields as `SecretStr` and returning the concrete model type.
- **Value-free doctor** — `doctor_data()` / the `vault_doctor` tool report each credential's `{layer, present}` provenance without ever returning a secret.
- **MCP tools** — `vault_doctor` (provenance), `vault_set` (keyring/config), and `vault_delete` (keyring removal) ship as `axm.tools` (MCP + CLI + DAG node).
- **Operator CLI** — `axm-vault` exposes `setup`/`get`/`set`/`rotate`/`delete`/`doctor`/`path`; interactive `setup` is TTY-guarded and idempotent, `get` masks secrets unless `--reveal`.
- **Frozen & strict** — immutable models that forbid unknown fields (`frozen=True`, `extra="forbid"`).

See the [documentation](https://forge.axm-protocols.io/axm-vault/) for the full guide, including [how to declare your package's credentials](docs/howto/declare-credentials.md).

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

## Start here

Follow the [isolated tutorial](docs/tutorials/getting-started.md), then [register a provider](docs/howto/declare-credentials.md). The README is the repository entry point; [docs/index.md](docs/index.md) is the site home.

`Resolver.resolve()` and `get()` return plaintext; `bind()` wraps SECRET fields in `SecretStr` when the consumer model accepts that type. Provenance omits resolved values but reads the underlying stores. File resolution applies to all sensitivities, and arbitrary provider/backend errors are not redacted. See [the security and I/O boundaries](docs/explanation/architecture.md).

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
