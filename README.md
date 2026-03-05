<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-audit — Code auditing and quality rules for Python projects</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-init/explanation/check-grades/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-audit/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-audit?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-audit/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-audit/"><img src="https://img.shields.io/pypi/v/axm-audit" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-audit/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

`axm-audit` audits Python project quality across **10 scored categories**, producing a composite **0–100 score** with an **A–F grade**. It works as a **CLI**, **Python API**, and **MCP tool** for AI agents.

📖 **[Full documentation](https://axm-protocols.github.io/axm-audit/)**

## Features

- 🔍 **Linting** — Ruff analysis (800+ rules)
- 🔒 **Type Checking** — Strict mypy (per-project `pyproject.toml` config)
- 📊 **Complexity** — Cyclomatic complexity via radon (Python API with subprocess fallback)
- 🛡️ **Security** — Bandit integration + hardcoded secrets detection
- 📦 **Dependencies** — Vulnerability scanning (pip-audit) + hygiene (deptry)
- 🧪 **Testing** — Coverage enforcement via pytest-cov
- 🏗️ **Architecture** — Circular imports, god classes, coupling metrics, duplication detection
- 📐 **Practices** — Docstring coverage, bare except detection, hardcoded secrets, blocking I/O, logging presence, test mirroring
- 🔧 **Tooling** — CLI tool availability checks
- 📈 **Composite Scoring** — Weighted 10-category 0–100 score with A–F grade

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

# Agent-optimized output (compact, actionable)
axm-audit audit . --agent

# Filter by category
axm-audit audit . --category lint

# Run tests with structured output (agent-optimized)
axm-audit test . --mode=compact
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

### MCP (AI Agent)

`axm-audit` is available as an MCP tool via [`axm-mcp`](https://github.com/axm-protocols/axm-mcp). AI agents can call `audit(path)` or `verify(path)` directly:

```python
# Agent-optimized output: passed checks as compact strings,
# failed checks as dicts with rule_id, message, details, fix_hint
from axm_audit.formatters import format_agent

data = format_agent(result)
# data["score"], data["grade"], data["passed"], data["failed"]
```

See the [MCP how-to guide](https://axm-protocols.github.io/axm-audit/howto/mcp/) for details.

## Scoring Model

10-category weighted composite on a 100-point scale:

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
| `lint` | `LintingRule`, `FormattingRule`, `DiffSizeRule`, `DeadCodeRule` | 4 |
| `type` | `TypeCheckRule` | 1 |
| `complexity` | `ComplexityRule` | 1 |
| `security` | `SecurityRule` (Bandit), `SecurityPatternRule` | 2 |
| `deps` | `DependencyAuditRule`, `DependencyHygieneRule` | 2 |
| `testing` | `TestCoverageRule` | 1 |
| `architecture` | `CircularImportRule`, `GodClassRule`, `CouplingMetricRule`, `DuplicationRule` | 4 |
| `practices` | `DocstringCoverageRule`, `BareExceptRule`, `BlockingIORule`, `LoggingPresenceRule`, `TestMirrorRule` | 5 |
| `structure` | `PyprojectCompletenessRule` | 1 |
| `tooling` | `ToolAvailabilityRule` | 3 |

## Development

```bash
git clone https://github.com/axm-protocols/axm-audit.git
cd axm-audit
uv sync --all-groups
uv run pytest           # 429 tests
uv run ruff check src/  # lint
uv run mypy src/        # type check
```

## License

Apache 2.0
