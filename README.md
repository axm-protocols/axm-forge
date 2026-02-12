# axm-audit

**Code auditing and quality rules for Python projects.**

<p align="center">
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-audit?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-audit/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔍 **Linting** — Ruff analysis (800+ rules)
- 🔒 **Type Checking** — Strict mypy via `mypy.api.run()`
- 📊 **Complexity** — Cyclomatic complexity via radon Python API
- 🛡️ **Security** — Bandit integration + hardcoded secrets detection
- 📦 **Dependencies** — Vulnerability scanning (pip-audit) + hygiene (deptry)
- 🧪 **Testing** — Coverage enforcement via pytest-cov
- 🏗️ **Architecture** — Circular imports, god classes, coupling metrics
- 📐 **Practices** — Docstring coverage, bare except detection
- 🔧 **Tooling** — CLI tool availability checks
- 📈 **Composite Scoring** — Weighted 8-category 0–100 score with A–F grade

## Installation

```bash
uv add axm-audit
```

## Quick Start

### CLI

```bash
# Full audit
axm-audit audit .

# JSON output
axm-audit audit . --json

# Filter by category
axm-audit audit . --category quality
```

### Python API

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

## Scoring Model

8-category weighted composite on a 100-point scale:

| Category | Weight | Tool |
|---|---|---|
| Linting | **20%** | Ruff |
| Type Safety | **15%** | mypy |
| Complexity | **15%** | radon |
| Security | **10%** | Bandit |
| Dependencies | **10%** | pip-audit + deptry |
| Testing | **15%** | pytest-cov |
| Architecture | **10%** | AST analysis |
| Practices | **5%** | AST analysis |

## Categories

| Category | Rules | Count |
|---|---|---|
| `quality` | `LintingRule`, `TypeCheckRule`, `ComplexityRule` | 3 |
| `security` | `SecurityRule` (Bandit) | 1 |
| `dependencies` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule` | 3 |
| `practice` | `DocstringCoverageRule`, `BareExceptRule`, `SecurityPatternRule` | 3 |
| `structure` | `PyprojectCompletenessRule` | 1 |
| `tooling` | `ToolAvailabilityRule` | 3 |

## Development

```bash
git clone https://github.com/axm-protocols/axm-audit.git
cd axm-audit
uv sync --all-groups
uv run pytest           # 186 tests
uv run ruff check src/  # lint
uv run mypy src/        # type check
```

## License

Apache 2.0
