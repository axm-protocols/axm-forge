"""Integration tests for CLI subcommands — real filesystem I/O.

Covers `axm-init check` on gold projects, `scaffold` with tmp_path fixtures,
and source-file inspection (real `open()` on the cli module).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.cli import app
from tests.integration._helpers import SCAFFOLD_ARGS


def _run(*args: str) -> tuple[str, str, int]:
    """Run CLI command and capture stdout/stderr/exit_code."""

    out, err = io.StringIO(), io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            app(args, exit_on_error=False)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception:
        exit_code = 1
    return out.getvalue(), err.getvalue(), exit_code


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
        'select = ["E","F","W","I","UP","B","SIM","S","BLE","PLR","N","RUF"]\n'
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
        "# test-pkg\n\n"
        "[![axm-audit](https://img.shields.io/badge/axm--audit-A-green)](.)\n"
        "[![axm-init](https://img.shields.io/badge/axm--init-A-green)](.)\n\n"
        "**desc**\n\n---\n\n## Features\n\n"
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
    (tests_dir / "test_x.py").write_text("def test_x() -> None: pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gen_ref_pages.py").write_text("")
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


class TestCheckCommand:
    """Tests for `axm-init check` — real-I/O scenarios on gold projects."""

    def test_empty_exits_1(self, tmp_path: Path) -> None:
        _stdout, _stderr, code = _run("check", str(tmp_path))
        assert code == 1

    def test_category_filter(self, gold_project: Path) -> None:
        stdout, _stderr, code = _run(
            "check", str(gold_project), "--category", "pyproject"
        )
        assert code == 0
        assert "pyproject" in stdout.lower()

    def test_invalid_category(self, gold_project: Path) -> None:
        _stdout, _stderr, code = _run("check", str(gold_project), "--category", "bad")
        assert code == 1


@patch("axm_init.adapters.copier.CopierAdapter")
def test_scaffold_no_name_defaults_to_dirname(
    mock_copier_cls: MagicMock, tmp_path: Path
) -> None:
    """When --name is omitted, project name defaults to directory name."""
    mock_adapter = mock_copier_cls.return_value
    mock_adapter.copy.return_value = type(
        "R", (), {"success": True, "files_created": [], "message": "ok"}
    )()

    target = tmp_path / "my-awesome-project"
    target.mkdir()
    stdout, _, code = _run("scaffold", str(target), *SCAFFOLD_ARGS)
    assert code == 0
    assert "my-awesome-project" in stdout


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(
            ("--name", "x", "--author", "A", "--email", "e@e.com"),
            id="missing-org",
        ),
        pytest.param(
            ("--name", "x", "--org", "o", "--email", "e@e.com"),
            id="missing-author",
        ),
        pytest.param(
            ("--name", "x", "--org", "o", "--author", "A"),
            id="missing-email",
        ),
    ],
)
def test_scaffold_missing_required_arg_exits(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    """Missing a required scaffold arg causes exit with error."""
    _, _, code = _run("scaffold", str(tmp_path), *args)
    assert code != 0


@patch("axm_init.adapters.copier.CopierAdapter")
def test_scaffold_license_holder_defaults_to_org(
    mock_copier_cls: MagicMock, tmp_path: Path
) -> None:
    """When --license-holder is omitted, it defaults to --org value."""
    mock_adapter = mock_copier_cls.return_value
    mock_adapter.copy.return_value = type(
        "R", (), {"success": True, "files_created": [], "message": "ok"}
    )()

    _run(
        "scaffold",
        str(tmp_path),
        "--name",
        "test-pkg",
        "--org",
        "my-org",
        "--author",
        "A",
        "--email",
        "e@e.com",
    )

    # Check that CopierConfig was created with license_holder = org
    call_args = mock_copier_cls.return_value.copy.call_args
    config = call_args[0][0]
    assert config.data["license_holder"] == "my-org"


@patch("axm_init.adapters.pypi.PyPIAdapter")
def test_scaffold_pypi_taken_exits_with_error(
    mock_cls: MagicMock, tmp_path: Path
) -> None:
    """--check-pypi with taken name causes exit code 1."""
    from axm_init.adapters.pypi import AvailabilityStatus

    mock_adapter = mock_cls.return_value
    mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

    _, _stderr, code = _run(
        "scaffold",
        str(tmp_path),
        "--name",
        "requests",
        "--check-pypi",
        *SCAFFOLD_ARGS,
    )
    assert code == 1


@patch("axm_init.adapters.pypi.PyPIAdapter")
def test_scaffold_pypi_taken_json_output(mock_cls: MagicMock, tmp_path: Path) -> None:
    """--check-pypi + --json outputs JSON error for taken name."""
    from axm_init.adapters.pypi import AvailabilityStatus

    mock_adapter = mock_cls.return_value
    mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

    stdout, _, code = _run(
        "scaffold",
        str(tmp_path),
        "--name",
        "requests",
        "--check-pypi",
        "--json",
        *SCAFFOLD_ARGS,
    )
    assert code == 1
    data = json.loads(stdout)
    assert "error" in data


@patch("axm_init.adapters.copier.CopierAdapter")
@patch("axm_init.adapters.pypi.PyPIAdapter")
def test_scaffold_pypi_error_continues(
    mock_cls: MagicMock, mock_copier_cls: MagicMock, tmp_path: Path
) -> None:
    """--check-pypi with network error continues (warning only)."""
    from axm_init.adapters.pypi import AvailabilityStatus

    mock_adapter = mock_cls.return_value
    mock_adapter.check_availability.return_value = AvailabilityStatus.ERROR
    mock_copier_adapter = mock_copier_cls.return_value
    mock_copier_adapter.copy.return_value = type(
        "R", (), {"success": True, "files_created": [], "message": "ok"}
    )()

    _, _, code = _run(
        "scaffold",
        str(tmp_path),
        "--name",
        "test-pkg",
        "--check-pypi",
        *SCAFFOLD_ARGS,
    )
    # Should not fail — availability check error is non-blocking
    assert code == 0


class TestScaffoldFailurePath:
    """Cover scaffold command failure output (copier fails)."""

    @patch("axm_init.adapters.copier.CopierAdapter")
    def test_scaffold_copier_fails_human(
        self, mock_copier_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Failed copier prints ❌ error to stderr."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R",
            (),
            {"success": False, "files_created": [], "message": "Template error"},
        )()
        _, stderr, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "fail-pkg",
            *SCAFFOLD_ARGS,
        )
        assert code == 1
        assert "❌" in stderr

    @patch("axm_init.adapters.copier.CopierAdapter")
    def test_scaffold_json_success(
        self, mock_copier_cls: MagicMock, tmp_path: Path
    ) -> None:
        """--json with successful scaffold outputs JSON with success=true."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": ["a.py"], "message": "ok"}
        )()
        stdout, _, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "my-pkg",
            "--json",
            *SCAFFOLD_ARGS,
        )
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True


class TestScaffoldPyPIJsonError:
    """Cover --check-pypi + --json error path (status=ERROR)."""

    @patch("axm_init.adapters.copier.CopierAdapter")
    @patch("axm_init.adapters.pypi.PyPIAdapter")
    def test_pypi_error_json_continues(
        self, mock_pypi: MagicMock, mock_copier: MagicMock, tmp_path: Path
    ) -> None:
        """--check-pypi + --json with ERROR status still continues."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.ERROR
        )
        mock_copier.return_value.copy.return_value = type(
            "R", (), {"success": True, "files_created": [], "message": "ok"}
        )()
        _stdout, _, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "pkg",
            "--check-pypi",
            "--json",
            *SCAFFOLD_ARGS,
        )
        assert code == 0


class TestScaffoldWithNameOption:
    """Tests for `--name` flag plumbing — invokes scaffold with tmp_path."""

    @patch("axm_init.adapters.copier.CopierAdapter")
    def test_scaffold_with_name_option(
        self, mock_copier_cls: MagicMock, tmp_path: Path
    ) -> None:
        """--name option is accepted and passed through."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": [], "message": "ok"}
        )()

        stdout, _, _ = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "test-project",
            "--org",
            "test-org",
            "--author",
            "Test",
            "--email",
            "t@t.com",
        )
        assert "test-project" in stdout
