# axm-vault

<p align="center">
  <strong>Catalog-resolver secrets manager (keyring + SecretStr) for AXM</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml">
    <img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-init.json" alt="axm-init" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-audit.json" alt="axm-audit" />
  </a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/coverage.json" alt="Coverage" />
  </a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## Installation

```bash
uv add axm-vault
```

## Quick Start

Declare the credentials a package needs — the catalog describes schema only,
keep real secrets out of its defaults and descriptions:

```python
from axm_vault import CredentialGroup, CredentialSpec

group = CredentialGroup(
    id="acme",
    package="axm-acme",
    title="Acme",
    specs=(CredentialSpec(name="api_key", env="ACME_API_KEY", kind="token"),),
)

spec = group.spec("api_key")  # -> CredentialSpec(name='api_key', ...)
```

The [isolated tutorial](tutorials/getting-started.md) resolves a synthetic value
using a temporary config home and an explicitly selected in-memory keyring.
A local group is accepted by `Resolver.resolve`; `get` and `bind` require a
[registered provider](howto/declare-credentials.md).

## Features

- ✅ **Value-less catalog** — models describe schema; default strings must not contain real secrets
- ✅ **Entry-point discovery** — `load_catalog()` aggregates `axm.credentials` groups (empty-safe, cached)
- ✅ **External authentication state** — value-less dependencies report `CONNECTED`, `DISCONNECTED`, or `TOOL_ABSENT` without exposing tokens
- ✅ **Layered resolution** — `Resolver` walks `env > file > keyring > default > prompt`; file tier delegated to `axm-config`, keyring only for `SECRET`
- ✅ **Typed binding** — `bind(model, group)` builds a pydantic model from resolved values, `SECRET` fields as `SecretStr`
- ✅ **Value-free doctor** — `doctor_data()` / `vault_doctor` report each credential's `{layer, present}` provenance per declared instance and surface skipped malformed contributions, without ever returning a secret
- ✅ **MCP tools** — `vault_doctor` (provenance), `vault_set` (keyring/config), and `vault_delete` (keyring removal) ship as `axm.tools` (MCP + CLI + DAG node)
- ✅ **Operator CLI** — `axm-vault` exposes `setup`/`get`/`set`/`rotate`/`delete`/`doctor`/`path`; interactive `setup` is TTY-guarded and idempotent, `get` masks secrets unless `--reveal`
- ✅ **Frozen & strict** — immutable pydantic v2 models that forbid unknown fields
- ✅ **Modern Python** — 3.12+ with strict typing

---

- [Get started](tutorials/getting-started.md)
- [Command reference](reference/cli.md)
- [Security and I/O boundaries](explanation/architecture.md)
