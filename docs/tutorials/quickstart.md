# Quick Start

Learn how to install axm-audit and run your first project audit.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
uv add axm-audit
```

## Run Your First Audit

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."))

print(f"Grade: {result.grade} ({result.quality_score:.1f}/100)")
print(f"Passed: {result.total - result.failed}/{result.total}")
print(f"All clear: {result.success}")
```

## Understand the Result

The `AuditResult` object contains:

| Property | Type | Description |
|----------|------|-------------|
| `checks` | `list[CheckResult]` | Individual check results |
| `success` | `bool` | `True` if all checks passed |
| `total` | `int` | Total number of checks |
| `failed` | `int` | Number of failed checks |
| `quality_score` | `float` | Composite score 0–100 |
| `grade` | `str` | Letter grade A–F |

## Inspect Individual Checks

```python
for check in result.checks:
    icon = "✅" if check.passed else "❌"
    print(f"{icon} {check.rule_id}: {check.message}")

    if not check.passed and check.fix_hint:
        print(f"   💡 {check.fix_hint}")
```

## Next Steps

- [Filter by category](../howto/categories.md) — focus on security, architecture, etc.
- [Understand the scoring](../explanation/scoring.md) — how the composite score works
- [Architecture overview](../explanation/architecture.md) — the 5-layer model
