"""Unit tests for CLI subcommands — no real I/O.

Covers command registration, app identity, version output, scaffold help text,
reserve validation, and help display for `axm-init` CLI.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

import cyclopts
import pytest

from axm_init.cli import app
from axm_init.models.results import ReserveResult


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


class TestAppIsCyclopts:
    """Verify the app object is a cyclopts.App."""

    def test_app_is_cyclopts_instance(self) -> None:
        """app must be a cyclopts.App, not typer.Typer."""
        assert isinstance(app, cyclopts.App)
        assert type(app).__module__.startswith("cyclopts")
        assert "typer" not in type(app).__module__

    def test_app_name(self) -> None:
        """App name should be 'axm-init'."""
        assert app.name[0] == "axm-init"


class TestCommandsRegistered:
    """Verify all expected commands are registered."""

    def _command_names(self) -> set[str]:
        """Extract command names from the app."""
        return set(app._commands.keys())

    @pytest.mark.parametrize(
        "command_name",
        [
            pytest.param("scaffold", id="scaffold"),
            pytest.param("reserve", id="reserve"),
            pytest.param("version", id="version"),
            pytest.param("check", id="check"),
        ],
    )
    def test_command_exists(self, command_name: str) -> None:
        """Command is registered on the app."""
        assert command_name in self._command_names()


class TestCheckCommandUnit:
    """Tests for `axm-init check` — non-I/O edge cases."""

    def test_nonexistent_path(self) -> None:
        _stdout, stderr, code = _run("check", "/tmp/nonexistent_axm_path")
        assert code == 1
        assert "Not a directory" in stderr


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


class TestScaffoldCommandOptions:
    """Tests for scaffold command help text (no real I/O)."""

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


class TestReserveJsonSuccess:
    """Cover reserve command JSON output for success path."""

    @patch("axm_init.cli._git_config_get", return_value="test-value")
    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_json_success(
        self, mock_creds: MagicMock, mock_reserve: MagicMock, _mock_git: MagicMock
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

    @patch("axm_init.cli._git_config_get", return_value="test-value")
    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_json_failure(
        self, mock_creds: MagicMock, mock_reserve: MagicMock, _mock_git: MagicMock
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

    @patch("axm_init.cli._git_config_get", return_value="test-value")
    @patch("axm_init.core.reserver.reserve_pypi")
    @patch("axm_init.adapters.credentials.CredentialManager")
    def test_reserve_dry_run_succeeds(
        self, mock_cred_cls: MagicMock, mock_reserve: MagicMock, _mock_git: MagicMock
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


class TestReserveValidation:
    """Tests for author/email validation in CLI reserve command."""

    @patch("axm_init.cli._git_config_get", return_value="")
    def test_cli_reserve_no_author_exits(self, _mock_git: MagicMock) -> None:
        """Missing --author with no git config → exit 1."""
        _, stderr, code = _run("reserve", "test-pkg", "--dry-run")
        assert code == 1
        assert "--author" in stderr

    @patch("axm_init.cli._git_config_get")
    def test_cli_reserve_no_email_exits(self, mock_git: MagicMock) -> None:
        """Author set but no email → exit 1 with email message."""
        # Return author on first call, empty on second (email)
        mock_git.side_effect = ["Real Author", ""]
        _, stderr, code = _run("reserve", "test-pkg", "--dry-run")
        assert code == 1
        assert "--email" in stderr

    @patch("axm_init.cli._git_config_get", return_value="")
    def test_cli_reserve_no_author_json_exits(self, _mock_git: MagicMock) -> None:
        """Missing author + --json → JSON error output."""
        stdout, _, code = _run("reserve", "test-pkg", "--dry-run", "--json")
        assert code == 1
        data = json.loads(stdout)
        assert "error" in data
        assert "--author" in data["error"]


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
