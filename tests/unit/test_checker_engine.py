"""Unit tests for CheckEngine, format_report, and format_json.

Covers the orchestration engine and both output formatters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine, format_json, format_report
from axm_init.models.check import CheckResult, Grade, ProjectResult

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_result(
    project_path: Path,
    *,
    passed: bool = True,
    score: int = 100,
) -> ProjectResult:
    """Build a minimal ProjectResult for formatter tests."""
    checks = [
        CheckResult(
            name="test.check",
            category="test",
            passed=passed,
            weight=10,
            message="ok" if passed else "missing",
            details=[] if passed else ["detail line"],
            fix="" if passed else "Run fix command",
        ),
    ]
    return ProjectResult.from_checks(project_path, checks)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def gold_project(tmp_path: Path) -> Path:
    """Minimal gold-standard project for engine tests."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\ndynamic = ["version"]\n'
        "classifiers = [\n"
        '    "Development Status :: 3 - Alpha",\n'
        '    "Programming Language :: Python :: 3.12",\n'
        '    "Typing :: Typed",\n]\n'
        "\n[project.urls]\n"
        'Homepage = "https://github.com/org/test-pkg"\n'
        'Documentation = "https://org.github.io/test-pkg/"\n'
        'Repository = "https://github.com/org/test-pkg.git"\n'
        'Issues = "https://github.com/org/test-pkg/issues"\n'
        "\n[build-system]\n"
        'requires = ["hatchling", "hatch-vcs"]\n'
        'build-backend = "hatchling.build"\n'
        "\n[dependency-groups]\n"
        'dev = ["pytest>=8.0","pytest-cov>=4.0","ruff>=0.8","mypy>=1.14","pre-commit>=4.0"]\n'  # noqa: E501
        'docs = ["mkdocs-material>=9.0","mkdocstrings[python]>=0.27",'
        '"mkdocs-gen-files>=0.5","mkdocs-literate-nav>=0.6"]\n'
        "\n[tool.mypy]\nstrict = true\npretty = true\n"
        "disallow_incomplete_defs = true\ncheck_untyped_defs = true\n"
        "\n[tool.ruff.lint]\n"
        'select = ["E","F","W","I","UP","B","SIM","S","RUF"]\n'
        "[tool.ruff.lint.per-file-ignores]\n"
        '"tests/*" = ["S101"]\n'
        "[tool.ruff.lint.isort]\n"
        'known-first-party = ["test_pkg"]\n'
        "\n[tool.pytest.ini_options]\n"
        'addopts = ["--strict-markers","--strict-config","--import-mode=importlib"]\n'
        'pythonpath = ["src"]\nfilterwarnings = ["error"]\n'
        "\n[tool.coverage.run]\nbranch = true\nrelative_files = true\n"
        "[tool.coverage.xml]\n"
        'output = "coverage.xml"\n'
        "[tool.coverage.report]\n"
        'exclude_lines = ["pragma: no cover"]\n'
        '\n[tool.git-cliff.changelog]\nheader = "# Changelog"\n'
    )
    # mkdocs
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n  - Tutorials:\n    - t.md\n  - How-To Guides:\n    - h.md\n"
        "  - Reference:\n    - r.md\n  - Explanation:\n    - e.md\n"
        "plugins:\n  - gen-files:\n      scripts: [docs/gen_ref_pages.py]\n"
        "  - literate-nav:\n      nav_file: SUMMARY.md\n  - mkdocstrings:\n"
    )
    # pre-commit
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: ruff\n    hooks:\n      - id: ruff\n      - id: ruff-format\n"
        "  - repo: mypy\n    hooks:\n      - id: mypy\n"
        "  - repo: conv\n    hooks:\n      - id: conventional-pre-commit\n"
        "  - repo: basic\n    hooks:\n      - id: trailing-whitespace\n"
        "      - id: end-of-file-fixer\n      - id: check-yaml\n"
    )
    # Makefile
    (tmp_path / "Makefile").write_text(
        ".PHONY: install check test format lint audit clean docs-serve\n"
        "install:\n\techo\ncheck:\n\techo\nlint:\n\techo\nformat:\n\techo\n"
        "test:\n\techo\naudit:\n\techo\nclean:\n\techo\ndocs-serve:\n\techo\n"
    )
    # CI
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
    # Files
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
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("def test_x(): pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gen_ref_pages.py").write_text("")
    # git hooks
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


# ── CheckEngine tests ────────────────────────────────────────────────────────


class TestCheckEngineRun:
    """Tests for CheckEngine.run()."""

    def test_run_all_categories(self, gold_project: Path) -> None:
        """Gold project scores 100 with all 39 checks."""
        engine = CheckEngine(gold_project)
        result = engine.run()
        assert result.score == 100
        assert result.grade == Grade.A
        assert len(result.checks) == 39

    def test_run_single_category(self, gold_project: Path) -> None:
        """Filtering to tooling returns only tooling checks."""
        engine = CheckEngine(gold_project, category="tooling")
        result = engine.run()
        assert all(c.category == "tooling" for c in result.checks)
        assert len(result.checks) == 7

    def test_run_invalid_category(self, gold_project: Path) -> None:
        """Invalid category raises ValueError."""
        engine = CheckEngine(gold_project, category="invalid")
        with pytest.raises(ValueError, match="Unknown category"):
            engine.run()


# ── Formatter tests ──────────────────────────────────────────────────────────


class TestFormatReport:
    """Tests for format_report()."""

    def test_contains_score_and_grade(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=True)
        report = format_report(result)
        assert "100" in report
        assert "A" in report

    def test_contains_failures(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=False)
        report = format_report(result)
        assert "❌" in report
        assert "Run fix command" in report


class TestFormatJson:
    """Tests for format_json()."""

    def test_structure(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=True)
        data = format_json(result)
        assert set(data.keys()) == {
            "project",
            "score",
            "grade",
            "categories",
            "checks",
            "failures",
        }
        assert data["score"] == 100
        assert data["grade"] == "A"

    def test_failures_list(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=False)
        data = format_json(result)
        assert len(data["failures"]) == 1
        assert data["failures"][0]["fix"] == "Run fix command"


class TestFormatAgent:
    """Tests for format_agent() — compact agent output."""

    def test_format_agent_all_passed(self, tmp_path: Path) -> None:
        """All passing → failed=[], passed_count is count of checks."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert output["failed"] == []
        assert output["passed_count"] == 1
        assert isinstance(output["passed_count"], int)

    def test_format_agent_with_failures(self, tmp_path: Path) -> None:
        """Failed items must have name, message, details, fix."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=False)
        output = format_agent(result)
        assert len(output["failed"]) == 1
        f = output["failed"][0]
        assert set(f.keys()) >= {"name", "message", "details", "fix"}

    def test_format_agent_has_required_keys(self, tmp_path: Path) -> None:
        """Agent output must have score, grade, passed_count, failed."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert set(output.keys()) == {"score", "grade", "passed_count", "failed"}

    def test_format_agent_no_passed_key(self, tmp_path: Path) -> None:
        """Agent output must NOT have a 'passed' key (replaced by count)."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert "passed" not in output


class TestFormatReportVerbose:
    """Tests for format_report() verbose flag."""

    def test_default_hides_individual_passed(self, tmp_path: Path) -> None:
        """Default output shows summary line, not individual check names."""
        result = _make_result(tmp_path, passed=True)
        report = format_report(result)
        assert "1 checks passed" in report
        assert "test.check" not in report

    def test_verbose_shows_individual_checks(self, tmp_path: Path) -> None:
        """Verbose output shows individual check names."""
        result = _make_result(tmp_path, passed=True)
        report = format_report(result, verbose=True)
        assert "test.check" in report
        assert "✅" in report

    def test_default_always_shows_failures(self, tmp_path: Path) -> None:
        """Failures are always shown in default mode."""
        result = _make_result(tmp_path, passed=False)
        report = format_report(result)
        assert "❌" in report
        assert "Run fix command" in report
