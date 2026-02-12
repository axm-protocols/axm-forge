# axm-init

**Python project scaffolding, auditing & governance CLI.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/audit-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-init?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-init/badge.svg?branch=main&v=2" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/typed-strict-blue" alt="Typed">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://axm-protocols.github.io/axm-init/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🚀 **Scaffold** — Bootstrap production-grade Python projects with Copier templates
- 📋 **Audit** — Score any project against the AXM gold standard (37 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish

## Installation

```bash
uv add axm-init
```

## Quick Start

```bash
# Scaffold a new project
axm-init init my-project \
  --org axm-protocols \
  --author "Your Name" --email "you@example.com"

# Audit against AXM standards
axm-init audit
# Score: 100/100 — Grade A 🏆

# Reserve a name on PyPI
axm-init reserve my-cool-lib --dry-run
```

## CLI Commands

### `axm-init init`

Scaffold a production-grade Python project (src layout, PEP 621, CI, docs).

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to initialize |
| `--org` | `-o` | *required* | GitHub org or username |
| `--author` | `-a` | *required* | Author name |
| `--email` | `-e` | *required* | Author email |
| `--name` | `-n` | *dir name* | Project name |
| `--license` | `-l` | `MIT` | License (MIT, Apache-2.0, EUPL-1.2) |
| `--license-holder` | | *--org* | License holder |
| `--description` | `-d` | | One-line description |
| `--check-pypi` | | `False` | Verify PyPI availability first |
| `--json` | | `False` | Output as JSON |

### `axm-init audit`

Score a project against the AXM gold standard (38 checks across 7 categories).

| Option | Short | Default | Description |
|---|---|---|---|
| `PATH` | | `.` | Directory to audit |
| `--category` | `-c` | *all* | Filter to one category |
| `--json` | | `False` | Output as JSON |

**Categories:** `pyproject`, `ci`, `tooling`, `docs`, `structure`, `deps`, `changelog`

### `axm-init reserve`

Reserve a package name on PyPI with a minimal placeholder.

| Option | Short | Default | Description |
|---|---|---|---|
| `NAME` | | *required* | Package name to reserve |
| `--author` | `-a` | `Gabriel Jarry` | Author name |
| `--email` | `-e` | `jarry.gabriel@gmail.com` | Author email |
| `--dry-run` | | `False` | Skip actual publish |
| `--json` | | `False` | Output as JSON |

## Development

```bash
git clone https://github.com/axm-protocols/axm-init.git
cd axm-init
uv sync --all-groups
uv run pytest           # 317 tests
uv run ruff check src/  # lint
```

## License

Apache License 2.0
