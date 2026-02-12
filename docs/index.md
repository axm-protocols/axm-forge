---
hide:
  - navigation
  - toc
---

# axm-init

<p align="center">
  <strong>Python project scaffolding CLI with Copier templates.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-init/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://axm-protocols.github.io/axm-init/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-init/gh-pages/badges/axm-init.json" alt="axm-init" /></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-init?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-init/badge.svg?branch=main" alt="Coverage" /></a>
  <a href="https://pypi.org/project/axm-init/"><img src="https://img.shields.io/pypi/v/axm-init" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/typed-strict-blue.svg" alt="Typed" />
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" /></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv" /></a>
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" />
</p>

---

## What is axm-init?

`axm-init` scaffolds production-grade Python projects with a single command. It generates fully configured projects with linting, typing, testing, CI/CD, and documentation out of the box.

## Quick Example

```bash
$ axm-init init my-project

✅ Project 'my-project' created at /path/to/my-project
   📄 pyproject.toml
   📄 src/my_project/__init__.py
   📄 tests/__init__.py
   📄 README.md
```

## Features

- 🚀 **Scaffold** — Bootstrap projects with Copier templates (`src/` layout, PEP 621)
- 📋 **Audit** — Score any project against the AXM gold standard (38 checks, A–F grade)
- 📦 **Reserve** — Claim a package name on PyPI before you're ready to publish
- ✅ **Standards** — Pre-configured Ruff, MyPy, Pytest, GitHub Actions
- 🔄 **Copier-powered** — Production-grade scaffolding with `src/` layout, PEP 621
- 📊 **JSON output** — Machine-readable output for CI integration

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/quickstart/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/cli/" class="md-button">CLI Reference</a>
</div>
