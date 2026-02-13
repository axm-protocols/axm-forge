---
hide:
  - navigation
  - toc
---

# axm-audit

<p align="center">
  <strong>Code auditing and quality rules for Python projects.</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-init.json" alt="axm-init" /></a>
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-audit.json" alt="axm-audit" /></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-audit?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-audit/badge.svg?branch=main" alt="Coverage" /></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" />
</p>

---

## What is axm-audit?

`axm-audit` is a Python library and CLI that audits project quality across 8 scored categories, producing a composite 0–100 score:

| Category | Tool | Weight |
|---|---|---|
| **Linting** | Ruff | 20% |
| **Type Safety** | mypy | 15% |
| **Complexity** | radon | 15% |
| **Security** | Bandit | 10% |
| **Dependencies** | pip-audit + deptry | 10% |
| **Testing** | pytest-cov | 15% |
| **Architecture** | AST analysis | 10% |
| **Practices** | AST analysis | 5% |

## Quick Example

```bash
# CLI
axm-audit audit .
```

```python
# Python API
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."))
print(f"Grade: {result.grade} — {result.quality_score:.1f}/100")
# Grade: A — 95.0/100
```

## Features

- 🔍 **Linting** — Ruff analysis (800+ rules)
- 🔒 **Type Safety** — Strict mypy via `mypy.api.run()`
- 📊 **Complexity** — Cyclomatic complexity via radon Python API
- 🛡️ **Security** — Bandit integration + hardcoded secrets detection
- 📦 **Dependencies** — Vulnerability scanning (pip-audit) + hygiene (deptry)
- 🧪 **Testing** — Coverage enforcement via pytest-cov
- 🏗️ **Architecture** — Circular imports, god classes, coupling metrics
- 📐 **Practices** — Docstring coverage, bare except detection
- 🔧 **Tooling** — CLI tool availability checks
- ⚡ **Fast & Typed** — Direct Python APIs, strict mypy, 208+ tests

---

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorials/getting-started/" class="md-button md-button--primary">Get Started →</a>
  <a href="reference/api/" class="md-button">API Reference</a>
</div>
