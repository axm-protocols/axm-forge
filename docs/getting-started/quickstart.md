# Quick Start

## Initialize a New Project

```bash
axm init my-project
cd my-project
```

This creates a production-ready Python project with:
- `pyproject.toml` with modern tooling
- `src/` layout
- `tests/` with pytest configuration
- Pre-configured linting and formatting

## Check Project Compliance

```bash
axm check
```

This verifies your project follows Python 2026 standards.

## Run a Full Audit

```bash
axm audit
```

Get a quality grade (A-F) with detailed analysis:

```
# Audit Report
**Grade:** A (92/100)
**Total:** 13 | **Passed:** 13 | **Failed:** 0
```

The audit checks:
- **Quality**: Lint, type coverage, complexity
- **Architecture**: Circular imports, coupling
- **Practice**: Docstrings, security patterns

## Reserve a Package Name

```bash
axm reserve my-package
```

Reserve your package name on PyPI before you're ready to publish.
