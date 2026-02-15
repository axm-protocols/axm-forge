---
hide:
  - navigation
  - toc
---

<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-init — Python project scaffolding, quality checks & governance CLI</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-init.json" alt="axm-init" /></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-audit.json" alt="axm-audit" /></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-init?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-init/badge.svg?branch=main" alt="Coverage" /></a>
  <a href="https://pypi.org/project/axm-init/"><img src="https://img.shields.io/pypi/v/axm-init" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <a href="https://axm-protocols.github.io/axm-init/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs" /></a>
</p>

---

## What is axm-init?

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
- 📋 **Check** — Score any project against the AXM gold standard (39 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish
- ✅ **Standards** — Pre-configured Ruff, MyPy, Pytest, GitHub Actions
- 📊 **JSON output** — Machine-readable output for CI integration

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/quickstart/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">CLI Reference</a>
</div>
