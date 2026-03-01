"""Shared fixtures for checks tests.

Provides gold-standard and empty project fixtures used across all
check module tests.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

GOLD_PYPROJECT = dedent("""\
    [project]
    name = "test-pkg"
    dynamic = ["version"]
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.12",
        "Typing :: Typed",
    ]

    [project.urls]
    Homepage = "https://github.com/org/test-pkg"
    Documentation = "https://org.github.io/test-pkg/"
    Repository = "https://github.com/org/test-pkg.git"
    Issues = "https://github.com/org/test-pkg/issues"

    [build-system]
    requires = ["hatchling", "hatch-vcs"]
    build-backend = "hatchling.build"

    [dependency-groups]
    dev = [
        "pytest>=8.0",
        "pytest-cov>=4.0",
        "ruff>=0.8",
        "mypy>=1.14",
        "pre-commit>=4.0",
    ]
    docs = [
        "mkdocs-material>=9.0",
        "mkdocstrings[python]>=0.27",
        "mkdocs-gen-files>=0.5",
        "mkdocs-literate-nav>=0.6",
    ]

    [tool.mypy]
    strict = true
    pretty = true
    disallow_incomplete_defs = true
    check_untyped_defs = true

    [tool.ruff.lint]
    select = ["E", "F", "W", "I", "UP", "B", "SIM", "S", "BLE", "PLR", "N", "RUF"]

    [tool.ruff.lint.per-file-ignores]
    "tests/*" = ["S101"]

    [tool.ruff.lint.isort]
    known-first-party = ["test_pkg"]

    [tool.pytest.ini_options]
    addopts = [
        "--strict-markers",
        "--strict-config",
        "--import-mode=importlib",
    ]
    pythonpath = ["src"]
    filterwarnings = ["error"]

    [tool.coverage.run]
    branch = true
    relative_files = true

    [tool.coverage.xml]
    output = "coverage.xml"

    [tool.coverage.report]
    exclude_lines = ["pragma: no cover"]

    [tool.git-cliff.changelog]
    header = "# Changelog"
""")

GOLD_MKDOCS = dedent("""\
    site_name: test-pkg
    nav:
      - Home: index.md
      - Tutorials:
        - Getting Started: tutorials/getting-started.md
      - How-To Guides:
        - howto/index.md
      - Reference:
        - CLI: reference/cli.md
      - Explanation:
        - Architecture: explanation/architecture.md
    plugins:
      - search
      - gen-files:
          scripts:
            - docs/gen_ref_pages.py
      - literate-nav:
          nav_file: SUMMARY.md
      - mkdocstrings:
          handlers:
            python:
              paths: [src]
""")

GOLD_PRECOMMIT = dedent("""\
    repos:
      - repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.8.6
        hooks:
          - id: ruff
          - id: ruff-format
      - repo: https://github.com/pre-commit/mirrors-mypy
        rev: v1.14.1
        hooks:
          - id: mypy
      - repo: https://github.com/compilerla/conventional-pre-commit
        rev: v3.6.0
        hooks:
          - id: conventional-pre-commit
            stages: [commit-msg]
      - repo: https://github.com/pre-commit/pre-commit-hooks
        rev: v5.0.0
        hooks:
          - id: trailing-whitespace
          - id: end-of-file-fixer
          - id: check-yaml
""")

GOLD_MAKEFILE = dedent("""\
    .PHONY: install check test format lint audit ci clean docs-serve

    install:
    \tuv sync --all-groups

    check: lint audit test

    lint:
    \tuv run ruff check src tests

    format:
    \tuv run ruff format src tests

    test:
    \tuv run pytest

    audit:
    \tuv run pip-audit

    clean:
    \trm -rf dist

    docs-serve:
    \tuv run mkdocs serve
""")

GOLD_CI = dedent("""\
    name: CI
    on:
      push:
        branches: [main]
    jobs:
      lint:
        name: Lint
        runs-on: ubuntu-latest
        steps:
          - run: make lint
      security:
        name: Security Audit
        runs-on: ubuntu-latest
        steps:
          - run: uv run pip-audit
      test:
        name: Test
        strategy:
          matrix:
            python-version: ["3.12", "3.13"]
        steps:
          - run: uv run pytest
      coverage-finish:
        steps:
          - uses: coverallsapp/github-action@v2
""")

GOLD_README = dedent("""\
    # test-pkg

    **A test package**

    <p align="center">
      <img src="https://img.shields.io/badge/CI-passing-green" alt="CI">
    </p>

    ---

    ## Features

    - ✅ Feature one

    ## Installation

    ```bash
    uv add test-pkg
    ```

    ## Quick Start

    ```python
    import test_pkg
    ```

    ## Development

    ```bash
    make install
    ```

    ## License

    MIT
""")


@pytest.fixture()
def gold_project(tmp_path: Path) -> Path:
    """Create a fully gold-standard project in tmp_path."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(GOLD_PYPROJECT)
    # mkdocs
    (tmp_path / "mkdocs.yml").write_text(GOLD_MKDOCS)
    # pre-commit
    (tmp_path / ".pre-commit-config.yaml").write_text(GOLD_PRECOMMIT)
    # Makefile
    (tmp_path / "Makefile").write_text(GOLD_MAKEFILE)
    # CI
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "ci.yml").write_text(GOLD_CI)
    # publish.yml with Trusted Publishing (OIDC)
    (ci_dir / "publish.yml").write_text(
        "name: Publish\npermissions:\n  id-token: write\n"
    )
    # dependabot
    (tmp_path / ".github" / "dependabot.yml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n"
    )
    # README
    (tmp_path / "README.md").write_text(GOLD_README)
    # CONTRIBUTING
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n")
    # LICENSE
    (tmp_path / "LICENSE").write_text("MIT License\n")
    # uv.lock
    (tmp_path / "uv.lock").write_text("version = 1\n")
    # .python-version
    (tmp_path / ".python-version").write_text("3.12\n")
    # src layout
    pkg_dir = tmp_path / "src" / "test_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "py.typed").write_text("")
    # tests
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_version.py").write_text("def test_v(): pass\n")
    # docs
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "gen_ref_pages.py").write_text("")
    # git hooks
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """An empty directory — worst case."""
    return tmp_path
