# Understanding Audit Grades

> **Goal:** Learn how AXM calculates project quality grades
> **Time:** 10 minutes
> **Prerequisites:** Completed [Quickstart](./quickstart.md)

## Overview

AXM's audit system grades your project from A to F based on Python 2026 engineering standards. This tutorial explains the scoring system and how to improve your grade.

## Step 1: Run Your First Audit

From your project directory:

```bash
axm audit
```

You'll see output like:

```
# Audit Report

**Status:** ❌ FAILED
**Grade:** B (78.0/100)
**Total:** 13 | **Passed:** 11 | **Failed:** 2

| Rule ID | Status | Message |
|---------|--------|---------|
| FILE_EXISTS_pyproject.toml | ✅ | pyproject.toml exists |
| QUALITY_TYPE | ❌ | Type score: 70/100 (3 errors) |
...
```

## Step 2: Understand the Grade Scale

| Grade | Score | Meaning |
|-------|-------|---------|
| **A** | 90-100 | Production-ready, follows all best practices |
| **B** | 80-89 | Good quality, minor improvements needed |
| **C** | 70-79 | Acceptable, several issues to address |
| **D** | 60-69 | Below standard, requires significant work |
| **F** | <60 | Failing, major structural issues |

## Step 3: Explore the 4 Audit Categories

### Structure Rules

Checks for essential project files:

```bash
axm audit --category structure
```

| Rule | Description |
|------|-------------|
| `pyproject.toml` | Modern build configuration |
| `README.md` | Project documentation |
| `src/` directory | Package source code |
| `tests/` directory | Test suite |

### Quality Rules

Checks code quality tooling:

```bash
axm audit --category quality
```

| Rule | Tool | Threshold |
|------|------|-----------|
| Linting | ruff | 0 errors |
| Type checking | mypy | 0 errors |
| Complexity | radon | CC ≤ 10 |

### Architecture Rules

Checks structural health:

```bash
axm audit --category architecture
```

| Rule | Description |
|------|-------------|
| Circular imports | No cross-module cycles |
| God classes | No class > 20 methods |
| Coupling | Low inter-module dependencies |

### Practice Rules

Checks coding standards:

```bash
axm audit --category practice
```

| Rule | Description |
|------|-------------|
| Docstrings | Public functions documented |
| Bare except | No `except:` without type |
| Security | No hardcoded secrets |

## Step 4: Filter by Category

Run only quality checks:

```bash
axm audit --category quality
```

Expected output:

```
# Audit Report

**Status:** ✅ PASSED
**Grade:** A (100.0/100)
**Total:** 3 | **Passed:** 3 | **Failed:** 0

| Rule ID | Status | Message |
|---------|--------|---------|
| QUALITY_LINT | ✅ | Lint score: 100/100 (0 issues) |
| QUALITY_TYPE | ✅ | Type score: 100/100 (0 errors) |
| QUALITY_COMPLEXITY | ✅ | Complexity score: 100/100 (0 high-complexity functions) |
```

## Step 5: Get JSON Output for CI

For automated pipelines, use JSON output:

```bash
axm audit --json
```

Example output:

```json
{
  "grade": "A",
  "score": 92,
  "total": 13,
  "passed": 13,
  "failed": 0,
  "checks": [
    {"name": "pyproject.toml exists", "passed": true},
    {"name": "README.md exists", "passed": true}
  ]
}
```

Use this in CI to enforce quality gates:

```bash
# Fail CI if grade drops below B
axm audit --json | jq -e '.score >= 80'
```

## Common Issues and Fixes

### Issue: Type checking failed

```
❌ Type checking (mypy): 3 errors found
```

**Fix:** Add type hints to your functions:

```python
# Before
def greet(name):
    return f"Hello, {name}"

# After
def greet(name: str) -> str:
    return f"Hello, {name}"
```

### Issue: Complexity too high

```
❌ Complexity: function_x has CC=15 (threshold: 10)
```

**Fix:** Break down complex functions into smaller ones.

### Issue: Missing docstrings

```
❌ Docstring coverage: 60% (threshold: 80%)
```

**Fix:** Add docstrings to public functions:

```python
def calculate_total(items: list[int]) -> int:
    """Calculate the sum of all items.

    Args:
        items: List of integers to sum.

    Returns:
        The total sum of all items.
    """
    return sum(items)
```

## What's Next?

- [CLI Reference](../reference/cli.md) — Full command options
- [Reserve a Package Name](./reserve-package.md) — Claim your name on PyPI
