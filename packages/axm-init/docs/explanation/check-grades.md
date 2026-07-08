# Understanding Check Grades

## Overview

`axm-init check` scores your project against the AXM gold standard — a set of 49 checks derived from the best practices embedded in the project template and CI configurations.

## Grade Scale

| Grade | Score Range | Meaning |
|-------|-----------|---------|
| **A** 🏆 | 90–100 | Gold standard — production-ready |
| **B** ✅ | 75–89 | Good — minor improvements needed |
| **C** ⚠️ | 60–74 | Acceptable — several gaps |
| **D** 🔧 | 40–59 | Below standard — significant work needed |
| **F** ❌ | 0–39 | Failing — major structural issues |

## Scoring System

Each check has a **weight** (1–4 points). The score is computed over the checks
that **actually run** for the project's context, not against a fixed point total:

```
Score = round(earned points / weight of executed checks × 100)
```

The denominator is **dynamic**. The check engine selects which checks run from the
project context (standalone, workspace, member) — a `WORKSPACE` adds the 19 workspace
points, while a member skips the checks listed in `SKIP_FOR_MEMBER` (e.g. CI and the
docs-group/`gen_ref_pages` checks, since those are owned by the monorepo root). The
result is always normalized to 0–100 and mapped to a grade using the boundaries above.

## The 8 Categories

### pyproject (29 pts)

Configuration completeness of `pyproject.toml`:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `pyproject.pyproject_exists` | 4 | File exists and is valid TOML |
| `pyproject.pyproject_urls` | 3 | Homepage, Documentation, Repository, Issues |
| `pyproject.pyproject_dynamic_version` | 3 | `dynamic = ["version"]` + hatch-vcs |
| `pyproject.pyproject_mypy` | 3 | strict, pretty, disallow_incomplete_defs, check_untyped_defs |
| `pyproject.pyproject_ruff` | 3 | per-file-ignores + known-first-party |
| `pyproject.pyproject_pytest` | 4 | strict-markers, strict-config, import-mode, pythonpath, filterwarnings |
| `pyproject.pyproject_coverage` | 4 | branch, relative_files, xml output, exclude_lines |
| `pyproject.pyproject_classifiers` | 1 | Development Status, Python version, Typing :: Typed |
| `pyproject.pyproject_ruff_rules` | 2 | Essential rules: E, F, I, UP, B, S, BLE, PLR, N |
| `pyproject.pyproject_wheel_doc_shipping` | 2 | Shipping docs wired through wheel `force-include` |

### ci (16 pts)

GitHub Actions CI workflow:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `ci.ci_workflow_exists` | 4 | `.github/workflows/ci.yml` exists |
| `ci.ci_lint_job` | 3 | Lint/type-check job |
| `ci.ci_test_job` | 3 | Test job with Python matrix |
| `ci.ci_security_job` | 2 | pip-audit security scanning |
| `ci.trusted_publishing` | 2 | OIDC Trusted Publishing without API token fallback |
| `ci.dependabot` | 2 | `.github/dependabot.yml` configured |

### tooling (16 pts)

Developer tooling configuration:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `tooling.precommit_exists` | 3 | `.pre-commit-config.yaml` exists |
| `tooling.precommit_ruff` | 2 | Ruff hook |
| `tooling.precommit_mypy` | 2 | MyPy hook |
| `tooling.precommit_conventional` | 2 | Conventional commits hook |
| `tooling.precommit_basic` | 1 | trailing-whitespace, end-of-file-fixer, check-yaml |
| `tooling.precommit_installed` | 2 | Pre-commit hooks activated in `.git/hooks/` |
| `tooling.makefile` | 4 | All standard targets (install, check, lint, format, test, audit, clean, docs-serve) |

### docs (16 pts)

Documentation setup:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `docs.mkdocs_exists` | 3 | `mkdocs.yml` exists |
| `docs.diataxis_nav` | 3 | Tutorials + How-To + Reference + Explanation |
| `docs.plugins` | 3 | gen-files, literate-nav, mkdocstrings |
| `docs.gen_ref_pages` | 2 | `docs/gen_ref_pages.py` for auto API docs |
| `docs.readme` | 3 | Features, Installation, Development, License sections |
| `docs.readme_badges` | 2 | axm-audit + axm-init badges in README |

### structure (17 pts)

Project structure:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `structure.src_layout` | 4 | `src/<pkg>/__init__.py` |
| `structure.py_typed` | 2 | PEP 561 `py.typed` marker |
| `structure.tests_dir` | 3 | `tests/` with `test_*.py` files |
| `structure.contributing` | 2 | `CONTRIBUTING.md` exists |
| `structure.license_file` | 3 | `LICENSE` file exists |
| `structure.uv_lock` | 2 | `uv.lock` committed for reproducible builds |
| `structure.python_version` | 1 | `.python-version` file for pinned Python |

### deps (5 pts)

Dependency groups:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `deps.dev_deps` | 3 | pytest, ruff, mypy, prek in dev group |
| `deps.docs_group` | 2 | mkdocs-material, mkdocstrings, gen-files, literate-nav |

!!! note "Members"
    `deps.docs_group` is skipped for workspace members — the docs dependencies
    live at the monorepo root, so a member only counts `deps.dev_deps` here.

### changelog (5 pts)

Changelog management:

| Check | Weight | What It Verifies |
|-------|--------|-----------------|
| `changelog.gitcliff_config` | 3 | `[tool.git-cliff]` in pyproject.toml |
| `changelog.no_manual_changelog` | 2 | No manual CHANGELOG.md (git-cliff auto-generates) |

### workspace (19 pts)

Workspace-specific checks — only run when the project context is `WORKSPACE`:

| Check | Weight | What It Verifies |
|-------|--------|------------------|
| `workspace.packages_layout` | 3 | Members live under `packages/` subdirectory |
| `workspace.members_consistent` | 2 | Each member has `pyproject.toml`, `src/`, `tests/` |
| `workspace.monorepo_plugin` | 2 | Root `mkdocs.yml` uses the `monorepo` plugin |
| `workspace.matrix_packages` | 2 | CI uses `--package` for per-member testing |
| `workspace.requires_python_compat` | 1 | Coherent `requires-python` across members |
| `workspace.root_name_collision` | 3 | Root project name does not collide with member names |
| `workspace.pytest_importmode` | 2 | Root pytest config has `import_mode = "importlib"` |
| `workspace.pytest_testpaths` | 2 | Root testpaths references member test directories |
| `workspace.quality_workflow` | 2 | `.github/workflows/axm-quality.yml` with per-package audit |

!!! note "Context-aware"
    Workspace checks are automatically skipped for standalone projects and workspace members.
    The check engine detects project context (standalone, member, workspace) from `[tool.uv.workspace]`.

## Improving Your Score

Every failed check includes a **Fix** instruction telling you exactly what to do. Run `axm-init check` iteratively until you reach Grade A.

!!! tip "Quick win"
    Projects scaffolded with `axm-init scaffold` start at **100/100** by default.
