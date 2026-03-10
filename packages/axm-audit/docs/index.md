<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-audit</h1>
<p align="center"><strong>Code auditing and quality rules for Python projects.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-audit/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
</p>

---

## What it does

`axm-audit` is a Python library and CLI that audits project quality across 10 scored categories, producing a composite 0–100 score:

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

# Or via the unified AXM CLI
axm audit .
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
- 🔒 **Type Safety** — Strict mypy (per-project `pyproject.toml` config)
- 📊 **Complexity** — Cyclomatic complexity via radon (Python API with subprocess fallback)
- 🛡️ **Security** — Bandit integration + hardcoded secrets detection
- 📦 **Dependencies** — Vulnerability scanning (pip-audit) + hygiene (deptry)
- 🧪 **Testing** — Coverage enforcement via pytest-cov
- 🏗️ **Architecture** — Circular imports, god classes, coupling metrics, duplication detection
- 📐 **Practices** — Docstring coverage, bare except detection, blocking I/O, logging presence, test mirroring
- 🔧 **Tooling** — CLI tool availability checks
- ⚡ **Fast & Typed** — Direct Python APIs, strict mypy, 429 tests, 93% coverage

## Learn More

- [Getting Started Tutorial](tutorials/getting-started.md)
- [Run an Audit](howto/audit.md)
- [Audit Categories](howto/categories.md)
- [CI Badge](howto/ci-badge.md)
- [Custom Rules](howto/custom-rules.md)
- [Use via MCP](howto/mcp.md)
- [Read Results](howto/results.md)
- [Troubleshooting](howto/troubleshooting.md)
- [Architecture](explanation/architecture.md)
- [Scoring](explanation/scoring.md)
- [Glossary](explanation/glossary.md)
