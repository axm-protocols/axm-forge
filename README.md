<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-init — Python project scaffolding, quality checks & governance CLI</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-init?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-init/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-init/"><img src="https://img.shields.io/pypi/v/axm-init" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-init/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>


---

## Features

- 🚀 **Scaffold** — Bootstrap production-grade Python projects with Copier templates
- 📋 **Check** — Score any project against the AXM gold standard (39 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish

## Installation

```bash
uv add axm-init
```

## Quick Start

```bash
# Scaffold a new project
axm-init scaffold my-project \
  --org axm-protocols \
  --author "Your Name" --email "you@example.com"

# Check against AXM standards
axm-init check
# Score: 100/100 — Grade A 🏆

# Reserve a name on PyPI
axm-init reserve my-cool-lib --dry-run
```

## CLI Commands

### `axm-init scaffold`

Scaffold a production-grade Python project (src layout, PEP 621, CI, docs).

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to initialize |
| `--org` | `-o` | *required* | GitHub org or username |
| `--author` | `-a` | *required* | Author name |
| `--email` | `-e` | *required* | Author email |
| `--name` | `-n` | *dir name* | Project name |
| `--license` | `-l` | `Apache-2.0` | License (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | *--org* | License holder |
| `--description` | `-d` | | One-line description |
| `--check-pypi` | | `False` | Verify PyPI availability first |
| `--json` | | `False` | Output as JSON |

### `axm-init check`

Score a project against the AXM gold standard (39 checks across 7 categories).

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to check |
| `--category` | `-c` | *all* | Filter to one category |
| `--json` | | `False` | Output as JSON |
| `--agent` | | `False` | Compact agent-friendly output |

**Categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`, `changelog`

### `axm-init reserve`

Reserve a package name on PyPI with a minimal placeholder.

| Option | Short | Default | Description |
|---|---|---|---|
| `NAME` | | *required* | Package name to reserve |
| `--author` | `-a` | *git config* | Author name (**required**) |
| `--email` | `-e` | *git config* | Author email (**required**) |
| `--dry-run` | | `False` | Skip actual publish |
| `--json` | | `False` | Output as JSON |

> **Note:** `--author` and `--email` fall back to `git config user.name` / `user.email`.
> If both are empty, `axm-init` exits with an error.

## CI Check Badge

Projects scaffolded with `axm-init scaffold` include an automated **check badge** that updates on every push. The badge shows your score and grade using the AXM logo.

```
push → axm-init check → badge JSON → gh-pages → shields.io
```

The badge is already in your README — just push to `main` and it appears after the first CI run.

**Existing projects** can add the badge too — copy `.github/workflows/axm-init.yml` from a scaffolded project and add the badge markup. See the [howto guide](https://axm-protocols.github.io/axm-init/howto/check/#ci-badge) for details.

## Development

```bash
git clone https://github.com/axm-protocols/axm-init.git
cd axm-init
uv sync --all-groups
uv run pytest           # 440 tests (fast subset, ~8s)
uv run pytest -m slow   # real Copier scaffold tests (~15s)
uv run ruff check src/  # lint
```

## License

Apache License 2.0
