<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-init</h1>
<p align="center"><strong>Python project scaffolding, quality checks & governance CLI.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-audit.json" alt="axm-audit"></a>
  <a href="https://forge.axm-protocols.io/init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-init/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-init/"><img src="https://img.shields.io/pypi/v/axm-init" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-init` scaffolds production-grade Python projects with a single command. It generates fully configured projects with linting, typing, testing, CI/CD, and documentation out of the box.

## Quick Example

```bash
$ axm-init scaffold my-project \
    --org axm-protocols --author "Your Name" --email "you@example.com"

✅ Project 'my-project' created at /path/to/my-project
   📄 pyproject.toml
   📄 src/my_project/__init__.py
   📄 tests/__init__.py
   📄 README.md
```

## Features

- 🚀 **Scaffold** — Bootstrap projects with Copier templates (`src/` layout, PEP 621)
- 📋 **Check** — Score any project against the AXM gold standard (44 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish
- ✅ **Standards** — Pre-configured Ruff, MyPy, Pytest, GitHub Actions
- 📊 **JSON output** — Machine-readable output for CI integration

## Learn More

- [Quick Start Tutorial](tutorials/quickstart.md)
- [Scaffold a Project](howto/scaffold.md)
- [Check Project Quality](howto/check.md)
- [Reserve a Name](howto/reserve.md)
- [Use via MCP](howto/mcp.md)
- [Architecture](explanation/architecture.md)
- [Check Grades](explanation/check-grades.md)
- [CLI Reference](reference/cli.md)
