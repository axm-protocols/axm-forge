# axm-init

**Python project scaffolding, auditing & governance CLI.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-init?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-init/badge.svg?branch=main" alt="Coverage"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/typed-strict-blue" alt="Typed">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://axm-protocols.github.io/axm-init/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🚀 **Scaffold** — Bootstrap production-grade Python projects with Copier templates
- 📋 **Audit** — Score any project against the AXM gold standard (31 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish

## Installation

```bash
uv add axm-init
```

## Quick Start

```bash
# Scaffold a new project
axm-init init my-project --name my-project

# Audit against AXM standards
axm-init audit
# Score: 100/100 — Grade A 🏆

# Reserve a name on PyPI
axm-init reserve my-cool-lib --dry-run
```

## Development

```bash
git clone https://github.com/axm-protocols/axm-init.git
cd axm-init
uv sync --all-groups
uv run pytest           # 288 tests
uv run ruff check src/  # lint
```

## License

Apache License 2.0
