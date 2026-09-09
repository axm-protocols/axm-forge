# Getting Started

This tutorial walks you through installing `axm-audit` and running your first project audit.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-audit
```

Or with pip:

```bash
pip install axm-audit
```

## Step 1: Run an Audit

### CLI

```bash
uv run axm audit . --json-output
```

### Python API

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."))
print("Grade:", result.grade, "Score:", result.quality_score)
```

The `AuditResult` contains every check result, a composite score, and a letter grade.

## Step 2: Inspect Results

```python
print(f"Passed: {result.total - result.failed}/{result.total}")

for check in result.checks:
    icon = "✅" if check.passed else "❌"
    print(f"{icon} {check.rule_id}: {check.message}")

    if not check.passed and check.fix_hint:
        print(f"   💡 {check.fix_hint}")
```

## Step 3: Filter by Category

Focus on a specific area:

```bash
# CLI
axm audit . --json-output --category lint
axm audit . --json-output --category security
```

```python
# Python API
result = audit_project(Path("."), category="lint")

# Quick mode (lint + type only, fastest)
result = audit_project(Path("."), quick=True)
```

!!! tip "Available categories"
    `lint`, `type`, `complexity`, `security`, `deps`,
    `testing`, `test_quality`, `architecture`, `practices`, `structure`, `tooling`

## Step 4: Get JSON Output

Use the Python API when you need the complete JSON-serializable payload:

```python
from axm_audit.formatters import format_json
import json

print(json.dumps(format_json(result), indent=2))
```

## Next Steps

- [Filter by category](../howto/categories.md) — all categories and their rules
- [Interpret results](../howto/results.md) — reporters, scoring, severity levels
- [Understand the scoring](../explanation/scoring.md) — how the composite score works
- [Architecture overview](../explanation/architecture.md) — layers and data flow

A fresh `uv add` environment exposes executables through `uv run`.
Prepare the target's mypy/stubs before type audits. Full audits can run
project tests and invoke dependency scanners; start with a category when
learning the tool. Node projects use [different tooling](../reference/frameworks.md).

A zero command exit means execution succeeded, not all checks passed.
Inspect JSON `failed`; for CI use the [explicit verdict gate](../howto/ci-badge.md).
