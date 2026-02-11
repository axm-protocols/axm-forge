# Understanding Audit Grades

## Overview

`axm-init audit` scores your project against the AXM gold standard — a set of 31 checks derived from the best practices embedded in the project template and CI configurations.

## Grade Scale

| Grade | Score Range | Meaning |
|-------|-----------|---------|
| **A** 🏆 | 90–100 | Gold standard — production-ready |
| **B** ✅ | 75–89 | Good — minor improvements needed |
| **C** ⚠️ | 60–74 | Acceptable — several gaps |
| **D** 🔧 | 40–59 | Below standard — significant work needed |
| **F** ❌ | 0–39 | Failing — major structural issues |

## Scoring System

Each of the 31 checks has a **weight** (1–5 points), totaling **100 points**.

```
Score = (earned points / total points) × 100
```

The score maps to a grade using the boundaries above.

## The 7 Categories

### pyproject (30 pts)

Configuration completeness of `pyproject.toml`:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `pyproject.exists` | 5 | File exists and is valid TOML |
| `pyproject.urls` | 3 | Homepage, Documentation, Repository, Issues |
| `pyproject.dynamic_version` | 4 | `dynamic = ["version"]` + hatch-vcs |
| `pyproject.mypy` | 4 | strict, pretty, disallow_incomplete_defs, check_untyped_defs |
| `pyproject.ruff` | 4 | per-file-ignores + known-first-party |
| `pyproject.pytest` | 5 | strict-markers, strict-config, import-mode, pythonpath, filterwarnings |
| `pyproject.coverage` | 5 | branch, relative_files, xml output, exclude_lines |

### ci (15 pts)

GitHub Actions CI workflow:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `ci.workflow_exists` | 5 | `.github/workflows/ci.yml` exists |
| `ci.lint_job` | 3 | Lint/type-check job |
| `ci.test_job` | 3 | Test job with Python matrix |
| `ci.security_job` | 2 | pip-audit security scanning |
| `ci.coverage_upload` | 2 | Coveralls or Codecov upload |

### tooling (15 pts)

Developer tooling configuration:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `tooling.precommit_exists` | 3 | `.pre-commit-config.yaml` exists |
| `tooling.precommit_ruff` | 2 | Ruff hook |
| `tooling.precommit_mypy` | 2 | MyPy hook |
| `tooling.precommit_conventional` | 2 | Conventional commits hook |
| `tooling.precommit_basic` | 1 | trailing-whitespace, end-of-file-fixer, check-yaml |
| `tooling.makefile` | 5 | All standard targets (install, check, lint, format, test, audit, clean, docs-serve) |

### docs (15 pts)

Documentation setup:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `docs.mkdocs_exists` | 3 | `mkdocs.yml` exists |
| `docs.diataxis_nav` | 4 | Tutorials + How-To + Reference + Explanation |
| `docs.plugins` | 3 | gen-files, literate-nav, mkdocstrings |
| `docs.gen_ref_pages` | 2 | `docs/gen_ref_pages.py` for auto API docs |
| `docs.readme` | 3 | Features, Installation, Development, License sections |

### structure (15 pts)

Project structure:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `structure.src_layout` | 5 | `src/<pkg>/__init__.py` |
| `structure.py_typed` | 2 | PEP 561 `py.typed` marker |
| `structure.tests_dir` | 3 | `tests/` with `test_*.py` files |
| `structure.contributing` | 2 | `CONTRIBUTING.md` exists |
| `structure.license` | 3 | `LICENSE` file exists |

### deps (5 pts)

Dependency groups:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `deps.dev_group` | 3 | pytest, ruff, mypy, pre-commit in dev group |
| `deps.docs_group` | 2 | mkdocs-material, mkdocstrings, gen-files, literate-nav |

### changelog (5 pts)

Changelog management:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `changelog.gitcliff` | 3 | `[tool.git-cliff]` in pyproject.toml |
| `changelog.no_manual` | 2 | No manual CHANGELOG.md (git-cliff auto-generates) |

## Improving Your Score

Every failed check includes a **Fix** instruction telling you exactly what to do. Run `axm-init audit` iteratively until you reach Grade A.

!!! tip "Quick win"
    Projects scaffolded with `axm-init init --template python` start at **100/100** by default.
