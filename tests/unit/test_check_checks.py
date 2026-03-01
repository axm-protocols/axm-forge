"""Unit tests for audit check functions — all 31 checks across 7 categories.

TDD RED — uses tmp_path fixtures to create gold-standard and broken projects.
Each check function has a pass and fail case.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from axm_init.models.check import CheckResult

import pytest

from axm_init.checks.changelog import check_gitcliff_config, check_no_manual_changelog
from axm_init.checks.ci import (
    check_ci_coverage_upload,
    check_ci_lint_job,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
    check_dependabot,
    check_trusted_publishing,
)
from axm_init.checks.deps import check_dev_deps, check_docs_deps
from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_gen_ref_pages,
    check_docs_plugins,
    check_mkdocs_exists,
    check_readme,
)
from axm_init.checks.pyproject import (
    check_pyproject_classifiers,
    check_pyproject_coverage,
    check_pyproject_dynamic_version,
    check_pyproject_exists,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
    check_pyproject_urls,
)
from axm_init.checks.structure import (
    check_contributing,
    check_license_file,
    check_py_typed,
    check_python_version,
    check_src_layout,
    check_tests_dir,
    check_uv_lock,
)
from axm_init.checks.tooling import (
    check_makefile,
    check_precommit_basic,
    check_precommit_conventional,
    check_precommit_exists,
    check_precommit_installed,
    check_precommit_mypy,
    check_precommit_ruff,
)
from axm_init.models.check import CheckResult

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — gold standard project
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Category 1: pyproject (7 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckPyprojectExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_exists(gold_project)
        assert r.passed is True
        assert r.weight == 4

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_pyproject_exists(empty_project)
        assert r.passed is False
        assert r.fix != ""

    def test_fail_corrupt(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("{{invalid toml")
        r = check_pyproject_exists(tmp_path)
        assert r.passed is False
        assert "unparsable" in r.message.lower() or "parse" in r.message.lower()


class TestCheckPyprojectUrls:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_urls(gold_project)
        assert r.passed is True

    def test_fail_missing_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False

    def test_fail_partial_urls(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[project.urls]\nHomepage = "h"\nRepository = "r"\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False
        assert "Documentation" in str(r.details) or "Issues" in str(r.details)


class TestCheckPyprojectDynamicVersion:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_dynamic_version(gold_project)
        assert r.passed is True

    def test_fail_no_dynamic(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_dynamic_version(tmp_path)
        assert r.passed is False


class TestCheckPyprojectMypy:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_mypy(gold_project)
        assert r.passed is True

    def test_fail_missing_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False

    def test_fail_partial(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[tool.mypy]\nstrict = true\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        assert "pretty" in str(r.details).lower()


class TestCheckPyprojectRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_per_file_ignores(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname="x"\n[tool.ruff.lint]\nselect=["E"]\n'
        )
        r = check_pyproject_ruff(tmp_path)
        assert r.passed is False


class TestCheckPyprojectPytest:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_pytest(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_pytest(tmp_path)
        assert r.passed is False


class TestCheckPyprojectCoverage:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_coverage(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_coverage(tmp_path)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 2: ci (5 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckCiWorkflowExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_workflow_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_ci_workflow_exists(empty_project)
        assert r.passed is False


class TestCheckCiLintJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_lint_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_lint_job(empty_project)
        assert r.passed is False


class TestCheckCiTestJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_test_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_test_job(empty_project)
        assert r.passed is False


class TestCheckCiSecurityJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_security_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_security_job(empty_project)
        assert r.passed is False


class TestCheckCiCoverageUpload:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_coverage_upload(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_coverage_upload(empty_project)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 3: tooling (6 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckPrecommitExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_precommit_exists(empty_project)
        assert r.passed is False


class TestCheckPrecommitRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_ruff(empty_project)
        assert r.passed is False


class TestCheckPrecommitMypy:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_mypy(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_mypy(empty_project)
        assert r.passed is False


class TestCheckPrecommitConventional:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_conventional(gold_project)
        assert r.passed is True

    def test_fail_no_hook(self, tmp_path: Path) -> None:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: x\n")
        r = check_precommit_conventional(tmp_path)
        assert r.passed is False


class TestCheckPrecommitBasic:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_basic(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_basic(empty_project)
        assert r.passed is False


class TestCheckMakefile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_makefile(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_makefile(empty_project)
        assert r.passed is False

    def test_fail_partial_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("install:\n\techo hi\n")
        r = check_makefile(tmp_path)
        assert r.passed is False
        assert len(r.details) > 0  # reports missing targets


class TestCheckPrecommitInstalled:
    def test_pass_hooks_installed(self, gold_project: Path) -> None:
        """Config exists + .git/hooks/pre-commit exists -> PASS."""
        r = check_precommit_installed(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_pass_no_config(self, empty_project: Path) -> None:
        """No .pre-commit-config.yaml -> PASS (nothing to install)."""
        r = check_precommit_installed(empty_project)
        assert r.passed is True

    def test_fail_config_no_hooks(self, tmp_path: Path) -> None:
        """Config exists but no .git/hooks/pre-commit -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
        assert "pre-commit install" in r.fix

    def test_fail_git_dir_no_hooks(self, tmp_path: Path) -> None:
        """.git/ exists but no hooks/ -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        (tmp_path / ".git").mkdir()
        r = check_precommit_installed(tmp_path)
        assert r.passed is False

    def test_fail_no_git_dir(self, tmp_path: Path) -> None:
        """Config exists but not a git repo -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 4: docs (5 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckMkdocsExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_mkdocs_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_mkdocs_exists(empty_project)
        assert r.passed is False


class TestCheckDiataxisNav:
    def test_pass(self, gold_project: Path) -> None:
        r = check_diataxis_nav(gold_project)
        assert r.passed is True

    def test_fail_flat_nav(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False

    def test_fail_partial(self, tmp_path: Path) -> None:
        mkdocs = "nav:\n  - Tutorials:\n    - t.md\n  - Reference:\n    - r.md\n"
        (tmp_path / "mkdocs.yml").write_text(mkdocs)
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False
        # Should report which Diátaxis sections are missing


class TestCheckDocsPlugins:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_plugins(gold_project)
        assert r.passed is True

    def test_fail_no_plugins(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
        r = check_docs_plugins(tmp_path)
        assert r.passed is False


class TestCheckDocsGenRefPages:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_gen_ref_pages(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_docs_gen_ref_pages(empty_project)
        assert r.passed is False


class TestCheckReadme:
    def test_pass(self, gold_project: Path) -> None:
        r = check_readme(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_readme(empty_project)
        assert r.passed is False

    def test_fail_no_features(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# test\n## Installation\n")
        r = check_readme(tmp_path)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 5: structure (5 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckSrcLayout:
    def test_pass(self, gold_project: Path) -> None:
        r = check_src_layout(gold_project)
        assert r.passed is True

    def test_fail_no_src(self, empty_project: Path) -> None:
        r = check_src_layout(empty_project)
        assert r.passed is False

    def test_fail_flat_layout(self, tmp_path: Path) -> None:
        pkg = tmp_path / "my_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        r = check_src_layout(tmp_path)
        assert r.passed is False


class TestCheckPyTyped:
    def test_pass(self, gold_project: Path) -> None:
        r = check_py_typed(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        r = check_py_typed(tmp_path)
        assert r.passed is False


class TestCheckTestsDir:
    def test_pass(self, gold_project: Path) -> None:
        r = check_tests_dir(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_tests_dir(empty_project)
        assert r.passed is False


class TestCheckContributing:
    def test_pass(self, gold_project: Path) -> None:
        r = check_contributing(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_contributing(empty_project)
        assert r.passed is False


class TestCheckLicenseFile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_license_file(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_license_file(empty_project)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 6: deps (2 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckDevDeps:
    def test_pass(self, gold_project: Path) -> None:
        r = check_dev_deps(gold_project)
        assert r.passed is True

    def test_fail_no_pyproject(self, empty_project: Path) -> None:
        r = check_dev_deps(empty_project)
        assert r.passed is False

    def test_fail_missing_deps(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[dependency-groups]\ndev = ["pytest"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is False


class TestCheckDocsDeps:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_deps(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[dependency-groups]\ndocs = ["mkdocs"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_docs_deps(tmp_path)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 7: changelog (2 checks)
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckGitcliffConfig:
    def test_pass(self, gold_project: Path) -> None:
        r = check_gitcliff_config(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_gitcliff_config(tmp_path)
        assert r.passed is False


class TestCheckNoManualChangelog:
    def test_pass(self, gold_project: Path) -> None:
        r = check_no_manual_changelog(gold_project)
        assert r.passed is True

    def test_fail_has_changelog(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        r = check_no_manual_changelog(tmp_path)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 8: new checks — pyproject.classifiers, pyproject.ruff_rules
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckPyprojectClassifiers:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_classifiers(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_no_classifiers(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False

    def test_fail_missing_typed(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\nclassifiers = ['
            '"Development Status :: 3 - Alpha",'
            '"Programming Language :: Python :: 3.12"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False
        assert "Typed" in str(r.details)


class TestCheckPyprojectRuffRules:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff_rules(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_no_select(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False

    def test_fail_missing_new_rules(self, tmp_path: Path) -> None:
        """Old 5-rule set should now fail — missing S, BLE, PLR, N."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "S" in missing
        assert "BLE" in missing
        assert "PLR" in missing
        assert "N" in missing

    def test_pass_with_all(self, tmp_path: Path) -> None:
        """select = ['ALL'] includes everything — should pass."""
        toml = '[project]\nname="x"\n[tool.ruff.lint]\nselect = ["ALL"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_pass_with_extend_select(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "S"]\n'
            'extend-select = ["I", "UP", "B", "BLE", "PLR", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_fail_subset_of_new_rules(self, tmp_path: Path) -> None:
        """Only S and N added — should fail listing BLE, PLR."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B", "S", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "BLE" in missing
        assert "PLR" in missing
        # S and N should NOT be in missing
        # (they're in the details string as context, check the sorted list)
        assert r.message == "Missing 2 essential ruff rule(s)"


# ─────────────────────────────────────────────────────────────────────────────
# Category 9: new checks — ci.trusted_publishing, ci.dependabot
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckTrustedPublishing:
    def test_pass_oidc(self, gold_project: Path) -> None:
        r = check_trusted_publishing(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_no_publish(self, empty_project: Path) -> None:
        r = check_trusted_publishing(empty_project)
        assert r.passed is False

    def test_fail_no_oidc(self, tmp_path: Path) -> None:
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "publish.yml").write_text("name: Publish\njobs:\n  build:\n")
        r = check_trusted_publishing(tmp_path)
        assert r.passed is False

    def test_fail_hybrid_token_and_oidc(self, tmp_path: Path) -> None:
        """id-token present but still using PYPI_API_TOKEN → not true OIDC."""
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "publish.yml").write_text(
            "name: Publish\npermissions:\n  id-token: write\n"
            "jobs:\n  publish:\n    steps:\n"
            "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
            "        with:\n"
            "          password: ${{ secrets.PYPI_API_TOKEN }}\n"
        )
        r = check_trusted_publishing(tmp_path)
        assert r.passed is False
        assert "PYPI_API_TOKEN" in r.fix


class TestCheckDependabot:
    def test_pass(self, gold_project: Path) -> None:
        r = check_dependabot(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_dependabot(empty_project)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Category 10: new checks — structure.uv_lock, structure.python_version
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckUvLock:
    def test_pass(self, gold_project: Path) -> None:
        r = check_uv_lock(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_uv_lock(empty_project)
        assert r.passed is False

    def test_pass_workspace_root(self, tmp_path: Path) -> None:
        """uv.lock at workspace root is detected for a member package."""
        # Workspace root
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        (tmp_path / "uv.lock").write_text("version = 1\n")
        # Member package (no local uv.lock)
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is True
        assert "workspace root" in r.message

    def test_fail_workspace_no_lock(self, tmp_path: Path) -> None:
        """Workspace root exists but has no uv.lock -> fail."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is False


class TestCheckPythonVersion:
    def test_pass(self, gold_project: Path) -> None:
        r = check_python_version(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_python_version(empty_project)
        assert r.passed is False


# ─────────────────────────────────────────────────────────────────────────────
# Cross-cutting: every failed check must have a non-empty fix
# ─────────────────────────────────────────────────────────────────────────────


class TestAllFailuresHaveFix:
    """Every check function, when failing, must provide a non-empty fix."""

    ALL_CHECKS: ClassVar[list[Callable[[Path], CheckResult]]] = [
        check_pyproject_exists,
        check_pyproject_urls,
        check_pyproject_dynamic_version,
        check_pyproject_mypy,
        check_pyproject_ruff,
        check_pyproject_pytest,
        check_pyproject_coverage,
        check_pyproject_classifiers,
        check_pyproject_ruff_rules,
        check_ci_workflow_exists,
        check_ci_lint_job,
        check_ci_test_job,
        check_ci_security_job,
        check_ci_coverage_upload,
        check_trusted_publishing,
        check_dependabot,
        check_precommit_exists,
        check_precommit_ruff,
        check_precommit_mypy,
        check_precommit_conventional,
        check_precommit_basic,
        check_makefile,
        check_mkdocs_exists,
        check_diataxis_nav,
        check_docs_plugins,
        check_docs_gen_ref_pages,
        check_readme,
        check_src_layout,
        check_py_typed,
        check_tests_dir,
        check_contributing,
        check_license_file,
        check_uv_lock,
        check_python_version,
        check_dev_deps,
        check_docs_deps,
        check_gitcliff_config,
        check_no_manual_changelog,
    ]

    @pytest.mark.parametrize(
        "check_fn",
        ALL_CHECKS,
        ids=[fn.__name__ for fn in ALL_CHECKS],
    )
    def test_failed_check_has_fix(
        self, check_fn: Callable[[Path], CheckResult], empty_project: Path
    ) -> None:
        # Some checks pass on empty projects (e.g. no_manual_changelog)
        r: CheckResult = check_fn(empty_project)
        if not r.passed:
            assert r.fix != "", f"{r.name} failed but has no fix instruction"
