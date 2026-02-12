"""Functional tests for the `axm-init check` CLI command.

TDD RED — tests the full audit command end-to-end.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.cli import app


def _run(*args: str) -> tuple[str, str, int]:
    """Run CLI command and capture stdout/stderr/exit_code."""
    out, err = io.StringIO(), io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            app(args)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    return out.getvalue(), err.getvalue(), exit_code


# Reuse the gold-standard fixture content from unit tests
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
    select = ["E", "F", "W", "I", "UP", "B", "SIM", "S", "RUF"]
    [tool.ruff.lint.per-file-ignores]
    "tests/*" = ["S101"]
    [tool.ruff.lint.isort]
    known-first-party = ["test_pkg"]

    [tool.pytest.ini_options]
    addopts = ["--strict-markers", "--strict-config", "--import-mode=importlib"]
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


@pytest.fixture()
def gold_project(tmp_path: Path) -> Path:
    """Create a fully compliant project."""
    (tmp_path / "pyproject.toml").write_text(GOLD_PYPROJECT)
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n  - Tutorials:\n    - t.md\n  - How-To Guides:\n    - h.md\n"
        "  - Reference:\n    - r.md\n  - Explanation:\n    - e.md\n"
        "plugins:\n  - gen-files:\n      scripts: [docs/gen_ref_pages.py]\n"
        "  - literate-nav:\n      nav_file: SUMMARY.md\n  - mkdocstrings:\n"
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: ruff\n    hooks:\n      - id: ruff\n      - id: ruff-format\n"
        "  - repo: mypy\n    hooks:\n      - id: mypy\n"
        "  - repo: conv\n    hooks:\n      - id: conventional-pre-commit\n"
        "  - repo: basic\n    hooks:\n      - id: trailing-whitespace\n"
        "      - id: end-of-file-fixer\n      - id: check-yaml\n"
    )
    (tmp_path / "Makefile").write_text(
        ".PHONY: install check test format lint audit clean docs-serve\n"
        "install:\n\techo\ncheck:\n\techo\nlint:\n\techo\nformat:\n\techo\n"
        "test:\n\techo\naudit:\n\techo\nclean:\n\techo\ndocs-serve:\n\techo\n"
    )
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "ci.yml").write_text(
        "jobs:\n  lint:\n    steps:\n      - run: make lint\n"
        "  security:\n    steps:\n      - run: pip-audit\n"
        "  test:\n    strategy:\n      matrix:\n        python-version: ['3.12']\n"
        "    steps:\n      - run: pytest\n"
        "  coverage:\n    steps:\n      - uses: coverallsapp/github-action@v2\n"
    )
    (ci_dir / "publish.yml").write_text(
        "name: Publish\npermissions:\n  id-token: write\n"
    )
    (tmp_path / ".github" / "dependabot.yml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n"
    )
    (tmp_path / "README.md").write_text(
        "# test-pkg\n\n**desc**\n\n---\n\n## Features\n\n"
        "## Installation\n\n## Quick Start\n\n## Development\n\n## License\n"
    )
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / ".python-version").write_text("3.12\n")
    pkg = tmp_path / "src" / "test_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "py.typed").write_text("")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x(): pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gen_ref_pages.py").write_text("")
    return tmp_path


class TestCheckGoldStandard:
    """Gold-standard project should score 100/100."""

    def test_score_100(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run("check", str(gold_project))
        assert code == 0
        assert "100" in stdout
        assert "A" in stdout

    def test_json_output(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run("check", str(gold_project), "--json")
        assert code == 0
        data = json.loads(stdout)
        assert data["score"] == 100
        assert data["grade"] == "A"
        assert len(data["failures"]) == 0


class TestCheckEmptyDir:
    """Empty directory should score 0/100."""

    def test_score_zero(self, tmp_path: Path) -> None:
        stdout, _stderr, code = _run("check", str(tmp_path))
        # Non-zero exit for failing audit
        assert "0" in stdout or code != 0
        assert "F" in stdout

    def test_json_grade_f(self, tmp_path: Path) -> None:
        stdout, _stderr, _code = _run("check", str(tmp_path), "--json")
        data = json.loads(stdout)
        assert data["grade"] == "F"
        # changelog.no_manual passes on empty dirs (2 pts)
        assert data["score"] <= 5


class TestCheckCategoryFilter:
    """--category flag should filter to one category."""

    def test_category_pyproject(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run(
            "check", str(gold_project), "--category", "pyproject"
        )
        assert code == 0
        assert "pyproject" in stdout.lower()

    def test_invalid_category(self, gold_project: Path) -> None:
        _stdout, _stderr, code = _run(
            "check", str(gold_project), "--category", "invalid"
        )
        assert code != 0


class TestCheckFailureReport:
    """Failures must include Fix: instructions."""

    def test_failures_have_fix(self, tmp_path: Path) -> None:
        # Minimal project — lots of failures
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        stdout, _stderr, _code = _run("check", str(tmp_path), "--json")
        data = json.loads(stdout)
        for failure in data["failures"]:
            assert failure["fix"] != "", f"{failure['name']} missing fix"


class TestCheckSelfTest:
    """axm-init itself should score ≥ B."""

    def test_self_audit(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        stdout, _stderr, _code = _run("check", str(project_root), "--json")
        data = json.loads(stdout)
        assert data["score"] >= 75, f"Self-check score too low: {data['score']}"
        assert data["grade"] in ("A", "B")
