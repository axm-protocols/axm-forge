<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-init — Project scaffolding, quality checks & governance tools</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-init/"><img src="https://img.shields.io/pypi/v/axm-init" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>


---

## Features

- 🚀 **Scaffold** — Bootstrap production-grade Python projects, workspaces, and member packages
- 📋 **Check** — Score any project against the AXM gold standard (context-selected checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish

## Installation

```bash
uv tool install --with axm-init axm
```

For a dependency inside an existing uv project, use `uv add axm-init`, then
invoke `uv run axm ...`.

## Quick Start

```bash
# Scaffold a new project
axm init_scaffold my-project \
  --org axm-protocols \
  --author "Your Name" --email "you@example.com"

# Check against AXM standards
axm init_check
# Score: 100/100 — Grade A 🏆

# Reserve a name on PyPI
axm init_reserve my-cool-lib --dry-run
```

## CLI Commands

### `axm init_scaffold`

Scaffold a production-grade Python project (src layout, PEP 621, CI, docs).

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to initialize |
| `--org` | | *required* | GitHub org or username |
| `--author` | | *required* | Author name |
| `--email` | | *required* | Author email |
| `--name` | | *dir name* | Project name |
| `--license` | | `Apache-2.0` | License (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | *--org* | License holder |
| `--description` | | | One-line description |
| `--workspace` | | `False` | Scaffold a UV workspace instead of a standalone package |
| `--member` | | | Scaffold a member sub-package with this name |
| `--check-pypi` | | `False` | Verify PyPI availability first |
| `--json-output` | | `False` | Output as JSON |

> **Note:** `--workspace` and `--member` are mutually exclusive.

### `axm init_check`

Score a project against the context- and framework-selected AXM checks.

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to check |
| `--category` | | *all* | Filter to one category |
| `--verbose` | | `False` | Show all checks including passed |
| `--json-output` | | `False` | Output as JSON |
| `--agent` | | `False` | Compact agent-friendly output |

**Python categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`, `changelog`, `workspace`, `paper`, `experiment`. Node/React/Svelte use their own registries.

### `axm init_reserve`

Reserve a package name on PyPI with a minimal placeholder.

| Option | Short | Default | Description |
|---|---|---|---|
| `NAME` | | *required* | Package name to reserve |
| `--author` | | *git config* | Author name (**required**) |
| `--email` | | *git config* | Author email (**required**) |
| `--dry-run` | | `False` | Skip actual publish |
| `--json-output` | | `False` | Output as JSON |

> **Note:** `--author` and `--email` fall back to `git config user.name` / `user.email`.
> Fallback occurs only if both flags are omitted. If one is supplied, the other
> must be supplied too; an incomplete identity is rejected.

See the [complete CLI reference](docs/reference/cli.md) for framework and protocol
options, output schemas and exit policy. The generated CLI has no short aliases.

## Workspace Support

`axm-init` detects five **project contexts** and adapts checks accordingly:

| Context | Detection | Behavior |
|---|---|---|
| **STANDALONE** | No `[tool.uv.workspace]` | All checks enabled |
| **WORKSPACE** | Has `[tool.uv.workspace]` at root | CI, tooling, and workspace checks enabled |
| **MEMBER** | Resolved uv workspace member | Shared checks redirected to root; inapplicable checks skipped |
| **PAPER** | Research markers | Paper form invariants |
| **EXPERIMENT** | Root manifest mapping with contract_version and id | Experiment form invariants |

### Per-Package Check Exclusions

Workspace members can exclude inapplicable checks via `pyproject.toml`.
Each entry is a prefix of a canonical check name — the
`category.function_name_without_check_` form shown in the report (e.g.
`ci.ci_steps_executable`). A bare category like `"ci"` excludes the whole
category:

```toml
[tool.axm-init]
exclude = ["ci.ci_steps_executable", "tooling.makefile"]
```

### Scaffold Modes

```bash
# Standalone package (default)
axm init_scaffold my-project --org myorg --author A --email e@e.com

# UV workspace
axm init_scaffold my-workspace --workspace --org myorg --author A --email e@e.com

# Member sub-package (run from inside workspace)
axm init_scaffold --member my-lib --org myorg --author A --email e@e.com
```

The `--member` flag auto-detects the workspace root, creates the package under `packages/<name>/`, and patches root files (Makefile, mkdocs.yml, pyproject.toml, CI workflows).

## CI Check Badge

Projects scaffolded with `axm init_scaffold` include an automated **check badge** that updates on every push. The badge shows your score and grade using the AXM logo.

```
push → axm init_check → badge JSON → gh-pages → shields.io
```

The badge is already in your README — just push to `main` and it appears after the first CI run.

**Existing projects** can add the badge too — copy `.github/workflows/axm-quality.yml` from a scaffolded project and add the badge markup. See the [howto guide](https://forge.axm-protocols.io/init/howto/check/#ci-badge) for details.

## Development

This package is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge) workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-init --directory packages/axm-init pytest -x -q
```

📖 **[Full documentation](https://forge.axm-protocols.io/init/)**

## License

Apache-2.0 — © 2026 axm-protocols
