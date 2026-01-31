# Quickstart: Your First Project with AXM

> **Goal:** Create a production-ready Python project and audit its quality
> **Time:** 5 minutes
> **Prerequisites:** Python 3.12+, pip or uv

## Overview

AXM (Axiom eXtensible Manager) is a CLI tool for Python project governance. In this tutorial, you'll initialize a new project and get your first quality grade.

## Step 1: Install AXM

```bash
# Using pip
pip install axm

# Or using uv (recommended)
uv pip install axm
```

Verify the installation:

```bash
axm version
```

Expected output:

```
axm 0.1.0
```

## Step 2: Initialize a New Project

Create a production-ready Python project with a single command:

```bash
axm init my-awesome-package
cd my-awesome-package/my-awesome-package
```

!!! note "Directory Structure"
    AXM creates a `my-awesome-package/my-awesome-package/` structure where the inner directory contains your actual project files.

Expected output:

```
✅ Project 'my-awesome-package' created at /path/to/my-awesome-package
```

This creates a complete project with:

- `pyproject.toml` — Modern build configuration with uv/hatch support
- `src/` layout — Industry-standard package structure
- `tests/` — Pre-configured pytest setup
- Git repository initialized with initial commit

## Step 3: Check Compliance

Run a compliance check:

```bash
axm check
```

Expected output:

```
# Audit Report

**Status:** ✅ PASSED
**Grade:** A (100.0/100)
**Total:** 13 | **Passed:** 13 | **Failed:** 0

| Rule ID | Status | Message |
|---------|--------|---------|
| FILE_EXISTS_pyproject.toml | ✅ | pyproject.toml exists |
| FILE_EXISTS_README.md | ✅ | README.md exists |
| DIR_EXISTS_src | ✅ | src/ exists |
| DIR_EXISTS_tests | ✅ | tests/ exists |
...
```

## Step 4: Run a Full Audit

Get a comprehensive quality grade:

```bash
axm audit
```

The audit checks 13 rules across 4 categories:

| Category | What It Checks |
|----------|---------------|
| Structure | `pyproject.toml`, `README.md`, `src/`, `tests/` |
| Quality | Lint (ruff), Types (mypy), Complexity (radon) |
| Architecture | Circular imports, god classes, coupling |
| Practice | Docstrings, bare except, security patterns |

## Step 5: Quick Audit (Optional)

For faster CI pipelines, use the quick mode:

```bash
axm audit --quick
```

This runs only lint + type checks (the fastest path to catch issues).

## What's Next?

- [Understanding Audit Grades](./audit-grades.md) — Deep dive into scoring
- [CLI Reference](../reference/cli.md) — Full command documentation
- [Reserve a Package Name](./reserve-package.md) — Claim your name on PyPI
