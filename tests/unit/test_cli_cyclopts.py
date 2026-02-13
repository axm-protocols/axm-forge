"""Unit tests for CLI — Cyclopts migration.

These tests verify the CLI uses Cyclopts (not Typer) and that all
commands are properly registered with correct signatures.
"""

from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import cyclopts

from axm_init.cli import app


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


class TestCommandsRegistered:
    """Verify all expected commands are registered."""

    def _command_names(self) -> set[str]:
        """Extract command names from the app."""
        return set(app._commands.keys())

    def test_init_command_exists(self) -> None:
        """init command is registered."""
        assert "init" in self._command_names()

    def test_reserve_command_exists(self) -> None:
        """reserve command is registered."""
        assert "reserve" in self._command_names()

    def test_version_command_exists(self) -> None:
        """version command is registered."""
        assert "version" in self._command_names()

    def test_check_command_exists(self) -> None:
        """check command is registered."""
        assert "check" in self._command_names()


class TestVersionCommand:
    """Tests for the version command output."""

    def _capture_version(self) -> str:
        """Run the version command and capture output."""
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(["version"], exit_on_error=False)
        except SystemExit:
            pass
        return f.getvalue()

    def test_version_output_contains_name(self) -> None:
        """version command outputs 'axm-init ...'."""
        output = self._capture_version()
        assert "axm-init" in output

    def test_version_output_format(self) -> None:
        """Output matches 'axm-init X.Y.Z' pattern."""
        output = self._capture_version()
        parts = output.strip().split()
        assert len(parts) == 2
        assert parts[0] == "axm-init"


class TestInitCommandOptions:
    """Tests for init command parameter signatures."""

    def _capture_help(self) -> str:
        """Run init --help and return output."""
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(["init", "--help"], exit_on_error=False)
        except SystemExit:
            pass
        return f.getvalue()

    def test_init_help_does_not_crash(self) -> None:
        """init --help runs without error."""
        output = self._capture_help()
        assert "init" in output.lower() or "path" in output.lower()

    def test_init_help_shows_org_flag(self) -> None:
        """init --help shows --org flag."""
        output = self._capture_help()
        assert "--org" in output

    def test_init_help_shows_author_flag(self) -> None:
        """init --help shows --author flag."""
        output = self._capture_help()
        assert "--author" in output

    def test_init_help_shows_email_flag(self) -> None:
        """init --help shows --email flag."""
        output = self._capture_help()
        assert "--email" in output

    def test_init_help_no_template_flag(self) -> None:
        """init --help must NOT show --template flag (removed)."""
        output = self._capture_help()
        assert "--template" not in output

    @patch("axm_init.cli.CopierAdapter")
    def test_init_with_name_option(
        self, mock_copier_cls: MagicMock, tmp_path: Path
    ) -> None:
        """--name option is accepted and passed through."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": [], "message": "ok"}
        )()

        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(
                    [
                        "init",
                        str(tmp_path),
                        "--name",
                        "test-project",
                        "--org",
                        "test-org",
                        "--author",
                        "Test",
                        "--email",
                        "t@t.com",
                    ],
                    exit_on_error=False,
                )
        except SystemExit:
            pass
        output = f.getvalue()
        assert "test-project" in output


class TestHelpDisplay:
    """Test that running without arguments or with --help shows help."""

    def test_help_shows_commands(self) -> None:
        """--help shows all registered commands."""
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(["--help"], exit_on_error=False)
        except SystemExit:
            pass
        output = f.getvalue()
        assert "init" in output
        assert "reserve" in output
        assert "version" in output


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
