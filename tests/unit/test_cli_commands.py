"""Unit tests for CLI commands (check, version, init).

Tests the CLI layer via the cyclopts app interface.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_init.cli import app
from axm_init.models.results import ScaffoldResult

# ── helpers ──────────────────────────────────────────────────────────────────


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


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def gold_project(tmp_path: Path) -> Path:
    """Minimal gold-standard project for CLI tests."""
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
        "dev = ["
        '"pytest>=8.0","pytest-cov>=4.0","ruff>=0.8",'
        '"mypy>=1.14","pre-commit>=4.0"]\n'
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
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("def test_x(): pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gen_ref_pages.py").write_text("")
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


# ── check command ────────────────────────────────────────────────────────────


class TestCheckCommand:
    """Tests for `axm-init check`."""

    def test_gold_exits_0(self, gold_project: Path) -> None:
        _stdout, _stderr, code = _run("check", str(gold_project))
        assert code == 0

    def test_empty_exits_1(self, tmp_path: Path) -> None:
        _stdout, _stderr, code = _run("check", str(tmp_path))
        assert code == 1

    def test_json_flag(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run("check", str(gold_project), "--json")
        assert code == 0
        data = json.loads(stdout)
        assert data["score"] == 100

    def test_category_filter(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run(
            "check", str(gold_project), "--category", "pyproject"
        )
        assert code == 0
        assert "pyproject" in stdout.lower()

    def test_invalid_category(self, gold_project: Path) -> None:
        _stdout, _stderr, code = _run("check", str(gold_project), "--category", "bad")
        assert code == 1

    def test_nonexistent_path(self) -> None:
        _stdout, stderr, code = _run("check", "/tmp/nonexistent_axm_path")
        assert code == 1
        assert "Not a directory" in stderr


# ── version command ──────────────────────────────────────────────────────────


class TestVersionCommand:
    """Tests for `axm-init version`."""

    def test_prints_version(self) -> None:
        stdout, _stderr, code = _run("version")
        assert code == 0
        assert "axm-init" in stdout


# ── init command (mocked) ────────────────────────────────────────────────────


class TestInitCommand:
    """Tests for `axm-init init` with mocked adapter."""

    def test_init_success(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml", "README.md"],
            message="ok",
        )
        with patch("axm_init.cli.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "init",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
            )
        assert code == 0
        assert "✅" in stdout

    def test_init_json_output(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml"],
            message="ok",
        )
        with patch("axm_init.cli.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "init",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
                "--json",
            )
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True

    def test_init_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=False,
            path=str(target),
            files_created=[],
            message="Copy failed",
        )
        with patch("axm_init.cli.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            _stdout, stderr, code = _run(
                "init",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
            )
        assert code == 1
        assert "❌" in stderr
