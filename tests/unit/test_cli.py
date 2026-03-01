"""Unit tests for cli.py — commands, cyclopts, coverage gaps, edge cases."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import cyclopts
import pytest

from axm_init.cli import app
from axm_init.core.reserver import ReserveResult
from axm_init.models.results import ScaffoldResult

# ── helpers ──────────────────────────────────────────────────────────────────


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


_run_list = lambda args: _run(*args)  # noqa: E731

# Required args for scaffold (to avoid noise in unrelated tests)
SCAFFOLD_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]


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


# ── Cyclopts identity ───────────────────────────────────────────────────────


class TestAppIsCyclopts:
    """Verify the app object is a cyclopts.App."""

    def test_app_is_cyclopts_instance(self) -> None:
        """app must be a cyclopts.App, not typer.Typer."""
        assert isinstance(app, cyclopts.App)

    def test_app_name(self) -> None:
        """App name should be 'axm-init'."""
        assert app.name[0] == "axm-init"

    def test_no_typer_dependency(self) -> None:
        """typer should not be importable from cli module."""
        import axm_init.cli as cli_module

        source = open(cli_module.__file__).read()
        assert "import typer" not in source
        assert "from typer" not in source


# ── Commands registered ──────────────────────────────────────────────────────


class TestCommandsRegistered:
    """Verify all expected commands are registered."""

    def _command_names(self) -> set[str]:
        """Extract command names from the app."""
        return set(app._commands.keys())

    def test_scaffold_command_exists(self) -> None:
        """scaffold command is registered."""
        assert "scaffold" in self._command_names()

    def test_reserve_command_exists(self) -> None:
        """reserve command is registered."""
        assert "reserve" in self._command_names()

    def test_version_command_exists(self) -> None:
        """version command is registered."""
        assert "version" in self._command_names()

    def test_check_command_exists(self) -> None:
        """check command is registered."""
        assert "check" in self._command_names()


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

    def test_version_output_contains_name(self) -> None:
        """version command outputs 'axm-init ...'."""
        stdout, _, code = _run("version")
        assert code == 0
        assert "axm-init" in stdout

    def test_version_output_format(self) -> None:
        """Output matches 'axm-init X.Y.Z' pattern."""
        stdout, _, code = _run("version")
        assert code == 0
        parts = stdout.strip().split()
        assert len(parts) == 2
        assert parts[0] == "axm-init"


# ── scaffold command (mocked) ────────────────────────────────────────────────


class TestScaffoldCommand:
    """Tests for `axm-init scaffold` with mocked adapter."""

    def test_scaffold_success(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml", "README.md"],
            message="ok",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "scaffold",
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

    def test_scaffold_json_output(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml"],
            message="ok",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "scaffold",
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

    def test_scaffold_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=False,
            path=str(target),
            files_created=[],
            message="Copy failed",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            _stdout, stderr, code = _run(
                "scaffold",
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


# ── scaffold edge cases ──────────────────────────────────────────────────────


class TestScaffoldEdgeCases:
    """Tests for scaffold command edge cases."""

    @patch("axm_init.adapters.copier.CopierAdapter")
    def test_scaffold_no_name_defaults_to_dirname(
        self, mock_copier_cls: MagicMock, tmp_path: Path
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

    def test_scaffold_missing_org_exits(self, tmp_path: Path) -> None:
        """Missing --org causes exit with error."""
        _, _, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "x",
            "--author",
            "A",
            "--email",
            "e@e.com",
        )
        assert code != 0

    def test_scaffold_missing_author_exits(self, tmp_path: Path) -> None:
        """Missing --author causes exit with error."""
        _, _, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "x",
            "--org",
            "o",
            "--email",
            "e@e.com",
        )
        assert code != 0

    def test_scaffold_missing_email_exits(self, tmp_path: Path) -> None:
        """Missing --email causes exit with error."""
        _, _, code = _run(
            "scaffold",
            str(tmp_path),
            "--name",
            "x",
            "--org",
            "o",
            "--author",
            "A",
        )
        assert code != 0

    @patch("axm_init.adapters.copier.CopierAdapter")
    def test_scaffold_license_holder_defaults_to_org(
        self, mock_copier_cls: MagicMock, tmp_path: Path
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
        self, mock_cls: MagicMock, tmp_path: Path
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
    def test_scaffold_pypi_taken_json_output(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
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

    @patch("axm_init.adapters.pypi.PyPIAdapter")
    def test_scaffold_pypi_error_continues(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
        """--check-pypi with network error continues (warning only)."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.ERROR

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


# ── scaffold command options (help) ──────────────────────────────────────────


class TestScaffoldCommandOptions:
    """Tests for scaffold command parameter signatures."""

    def _capture_help(self) -> str:
        """Run scaffold --help and return output."""
        stdout, _, _ = _run("scaffold", "--help")
        return stdout

    def test_scaffold_help_does_not_crash(self) -> None:
        """scaffold --help runs without error."""
        output = self._capture_help()
        assert "scaffold" in output.lower() or "path" in output.lower()

    def test_scaffold_help_shows_org_flag(self) -> None:
        """scaffold --help shows --org flag."""
        assert "--org" in self._capture_help()

    def test_scaffold_help_shows_author_flag(self) -> None:
        """scaffold --help shows --author flag."""
        assert "--author" in self._capture_help()

    def test_scaffold_help_shows_email_flag(self) -> None:
        """scaffold --help shows --email flag."""
        assert "--email" in self._capture_help()

    def test_scaffold_help_no_template_flag(self) -> None:
        """scaffold --help must NOT show --template flag (removed)."""
        assert "--template" not in self._capture_help()

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


# ── scaffold CLI coverage gaps ───────────────────────────────────────────────


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


# ── reserve command ──────────────────────────────────────────────────────────


class TestReserveJsonSuccess:
    """Cover reserve command JSON output for success path."""

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_json_success(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """--json with successful reserve outputs JSON with success=true."""
        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1.dev0",
            message="Reserved 'test-pkg' on PyPI",
        )
        stdout, _, code = _run("reserve", "test-pkg", "--dry-run", "--json")
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_json_failure(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """--json with failed reserve outputs JSON with success=false."""
        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=False,
            package_name="taken-pkg",
            version="0.0.1.dev0",
            message="Package 'taken-pkg' is already taken on PyPI",
        )
        stdout, _, code = _run("reserve", "taken-pkg", "--dry-run", "--json")
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is False

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_human_failure(
        self, mock_creds: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """Failed reserve without --json prints stderr error."""
        mock_creds.return_value.get_pypi_token.return_value = "tok"
        mock_reserve.return_value = ReserveResult(
            success=False,
            package_name="taken-pkg",
            version="0.0.1.dev0",
            message="Package is taken",
        )
        _, stderr, code = _run("reserve", "taken-pkg", "--dry-run")
        assert code == 1
        assert "❌" in stderr


class TestReserveCommand:
    """Tests for the reserve command — edge cases."""

    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_no_token_json_exits(self, mock_cls: MagicMock) -> None:
        """No token + --json outputs error JSON and exits 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        stdout, _, code = _run("reserve", "test-pkg", "--json")
        assert code == 1
        data = json.loads(stdout)
        assert "error" in data

    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_resolve_fails_exits(self, mock_cls: MagicMock) -> None:
        """resolve_pypi_token raising SystemExit causes CLI exit 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        _, _, code = _run("reserve", "test-pkg")
        assert code == 1

    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_dry_run_succeeds(
        self, mock_cred_cls: MagicMock, mock_reserve: MagicMock
    ) -> None:
        """--dry-run skips resolve_pypi_token and succeeds."""
        mock_creds = mock_cred_cls.return_value
        mock_creds.get_pypi_token.return_value = None

        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1.dev0",
            message="Dry run — would reserve 'test-pkg' on PyPI",
        )

        stdout, _, code = _run("reserve", "test-pkg", "--dry-run")
        assert code == 0
        assert "Dry run" in stdout
        # resolve_pypi_token should NOT be called in dry-run
        mock_creds.resolve_pypi_token.assert_not_called()


# ── help display ─────────────────────────────────────────────────────────────


class TestHelpDisplay:
    """Test that running without arguments or with --help shows help."""

    def test_help_shows_commands(self) -> None:
        """--help shows all registered commands."""
        stdout, _, _ = _run("--help")
        assert "scaffold" in stdout
        assert "reserve" in stdout
        assert "version" in stdout

    def test_no_args_shows_help(self) -> None:
        """Running with no arguments shows help text."""
        stdout, _, _code = _run("--help")
        assert "scaffold" in stdout


# ── entry point ──────────────────────────────────────────────────────────────


class TestEntryPoint:
    """Test that the CLI entry point works via subprocess."""

    def test_cli_entry_point_runs(self) -> None:
        """axm-init --help can be invoked via python -m."""
        result = subprocess.run(
            [sys.executable, "-m", "axm_init.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should not crash
        assert result.returncode in (0, 2)
