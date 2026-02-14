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
axm-audit audit .

# Or via the unified AXM CLI
axm audit .
```

### Python API

```python
from pathlib import Path
from axm_audit import audit_project

result = audit_project(Path("."))
print(f"Grade: {result.grade} — {result.quality_score:.1f}/100")
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
axm-audit audit . --category quality
axm-audit audit . --category security
```

```python
# Python API
result = audit_project(Path("."), category="quality")

# Quick mode (lint + type only, fastest)
result = audit_project(Path("."), quick=True)
```

!!! tip "Available categories"
    `quality`, `security`, `dependencies`, `testing`,
    `architecture`, `practice`, `structure`, `tooling`

## Step 4: Get JSON Output

```bash
axm-audit audit . --json
```

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
