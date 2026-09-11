<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-vault — Credential catalogs, layered resolution and keyring storage</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-vault/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-vault/"><img src="https://img.shields.io/pypi/v/axm-vault" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/axm-vault/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

axm-vault separates credential declarations from value resolution and storage.
Packages declare their needs; applications resolve values through environment,
configuration and keyring layers, with optional prompts and Pydantic binding.

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

Requires Python 3.12 or newer. In a project managed by uv:

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

## Quick Start

Declare a credential schema and mask a synthetic value without consulting your
configuration or keyring:

```bash
uv run python - <<'PY'
from axm_vault import CredentialGroup, CredentialSpec, as_secret

group = CredentialGroup(
    id="demo",
    package="demo-app",
    title="Demo service",
    specs=(CredentialSpec(name="token", env="DEMO_TOKEN", kind="token"),),
)
print(group.spec("token").env)
print(as_secret("synthetic-example"))
PY
```

This prints `DEMO_TOKEN` and `**********`. The declaration contains no credential
value. Creating a group does not register it with the installed catalog; follow
[Declare credentials](docs/howto/declare-credentials.md) to contribute a provider.
For actual resolution with isolated stores, use the
[synthetic credential tutorial](docs/tutorials/getting-started.md).

## Usage

### Python API

Use `Resolver.resolve(group, name)` with an explicit group, or catalog-based
`get(group, name)` and `bind(model, group)` after registering a provider.
`load_catalog()` discovers installed `axm.credentials` entry points and caches
the catalog. Consumer models used with `bind()` must accept `SecretStr` for
SECRET fields.

### CLI and AXM tools

```bash
uv run axm-vault --help
uv run axm vault_doctor --help
```

The operator CLI provides `setup`, `get`, `set`, `rotate`, `delete`, `doctor`
and `path`. Interactive `setup` requires a TTY; blank input preserves existing
values. Omit the value argument from standalone `set` or `rotate` to enter it
through a hidden prompt instead of shell history or process arguments.

The `vault_doctor`, `vault_set` and `vault_delete` tools also support the generic
`axm` CLI and MCP discovery. `vault_set` requires a value argument and has no
hidden-input mode. See the [CLI reference](docs/reference/cli.md) for parameters.

### Security and operational boundaries

`Resolver.resolve()` and `get()` return plaintext; `bind()` wraps SECRET fields in `SecretStr` when the consumer model accepts that type. Provenance omits resolved values but reads the underlying stores. File resolution applies to all sensitivities, and arbitrary provider/backend errors are not redacted. See [the security and I/O boundaries](docs/explanation/architecture.md).

The selected keyring backend determines storage protection; `SecretStr` masks
representations, it does not encrypt data. Deletion removes a keyring slot,
leaving file/environment overrides and the rotation backup intact.
Authentication dependencies are separate from credential provenance:
`vault_doctor` does not check authentication sessions; `axm-doctor` consumes
those status descriptors.

## Documentation

- [Published documentation](https://forge.axm-protocols.io/axm-vault/)
- [Isolated getting-started tutorial](docs/tutorials/getting-started.md)
- [Declare package credentials](docs/howto/declare-credentials.md)
- [Resolver](docs/reference/resolver.md)
- [Doctor and tools](docs/reference/doctor.md)
- [Architecture and security boundaries](docs/explanation/architecture.md)

The README is the repository entry point; [docs/index.md](docs/index.md) is the
MkDocs home page.

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) uv workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-packages --all-groups

# Run tests for this package
uv run --package axm-vault --directory packages/axm-vault pytest -x -q

# Build this package's documentation
uv run --package axm-vault --directory packages/axm-vault --group docs mkdocs build --strict
```

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).
