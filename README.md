# axm-audit

**Code auditing and quality rules for Python projects.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-audit?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-audit/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/typed-strict-blue" alt="Typed">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔍 **Linting** — Score code quality with Ruff (800+ rules)
- 🔒 **Type Checking** — Strict mypy analysis via `mypy.api.run()`
- 📊 **Complexity** — Cyclomatic complexity via radon Python API
- 🛡️ **Security** — Pattern-based vulnerability detection
- 🏗️ **Architecture** — Circular imports, god classes, coupling metrics
- 📐 **Practices** — Docstring coverage, bare except detection
- 📈 **Composite Scoring** — Weighted 0–100 score with A–F grade

## Installation

```bash
uv add axm-audit
```

## Quick Start

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."))

print(f"Grade: {result.grade} ({result.quality_score:.1f}/100)")
print(f"Checks: {result.total - result.failed}/{result.total} passed")

for check in result.checks:
    if not check.passed:
        print(f"  ❌ {check.rule_id}: {check.message}")
        if check.fix_hint:
            print(f"     Fix: {check.fix_hint}")
```

## Python API

| Function | Description |
|---|---|
| `audit_project(path)` | Run all checks, return `AuditResult` |
| `audit_project(path, category="quality")` | Filter to one category |
| `audit_project(path, quick=True)` | Lint + type checks only |
| `get_rules_for_category(cat)` | Get rule instances for a category |

### Categories

| Category | Rules | Tool |
|---|---|---|
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | Ruff, MyPy, Radon |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | AST |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | AST |
| `structure` | `FileExistsRule`, `DirectoryExistsRule` | Filesystem |

### Quality Score Weights

| Layer | Weight |
|---|---|
| Lint (Ruff) | **40%** |
| Type (MyPy) | **35%** |
| Complexity (Radon) | **25%** |

## Development

```bash
git clone https://github.com/axm-protocols/axm-audit.git
cd axm-audit
uv sync --all-groups
uv run pytest           # 106 tests
uv run ruff check src/  # lint
```

## License

MIT
