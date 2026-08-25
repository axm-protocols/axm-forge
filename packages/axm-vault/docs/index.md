---
hide:
  - navigation
  - toc
---

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
it never holds a secret value:

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

Resolve a value by walking the layer precedence
(`env > file > keyring > default > prompt`) — the file tier is delegated to
`axm-config`, the keyring tier is consulted only for `SECRET` specs:

```python
from axm_vault import Resolver, get

resolved = Resolver().resolve(group, "api_key")
resolved.value, resolved.layer   # e.g. ("s3cr3t", "env")

api_key = get("acme", "api_key")  # singleton convenience -> just the value
```

## Features

- ✅ **Value-less catalog** — models describe credential schema only, never store a secret
- ✅ **Entry-point discovery** — `load_catalog()` aggregates `axm.credentials` groups (empty-safe, cached)
- ✅ **Layered resolution** — `Resolver` walks `env > file > keyring > default > prompt`; file tier delegated to `axm-config`, keyring only for `SECRET`
- ✅ **Typed binding** — `bind(model, group)` builds a pydantic model from resolved values, `SECRET` fields as `SecretStr`
- ✅ **Value-free doctor** — `doctor_data()` / `vault_doctor` report each credential's `{layer, present}` provenance without ever returning a secret
- ✅ **MCP tools** — `vault_doctor` (provenance) and `vault_set` (keyring/config) ship as `axm.tools` (MCP + CLI + DAG node)
- ✅ **Operator CLI** — `axm-vault` exposes `setup`/`get`/`set`/`rotate`/`doctor`/`path`; interactive `setup` is TTY-guarded and idempotent, `get` masks secrets unless `--reveal`
- ✅ **Frozen & strict** — immutable pydantic v2 models that forbid unknown fields
- ✅ **Modern Python** — 3.12+ with strict typing
- ✅ **Tested** — Full coverage with pytest

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">Reference</a>
</div>
