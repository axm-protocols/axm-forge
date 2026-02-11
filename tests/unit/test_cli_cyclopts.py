"""Unit tests for CLI — Cyclopts migration.

These tests verify the CLI uses Cyclopts (not Typer) and that all
commands are properly registered with correct signatures.
"""

from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

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

    def test_audit_command_exists(self) -> None:
        """audit command is registered (Phase C)."""
        assert "audit" in self._command_names()


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

    def test_init_help_does_not_crash(self) -> None:
        """init --help runs without error."""
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(["init", "--help"], exit_on_error=False)
        except SystemExit:
            pass
        output = f.getvalue()
        assert "init" in output.lower() or "path" in output.lower()

    @patch("axm_init.cli.CopierAdapter")
    @patch("axm_init.cli.resolve_template")
    def test_init_with_name_option(
        self, mock_resolve, mock_copier_cls, tmp_path
    ) -> None:
        """--name option is accepted as Annotated parameter."""
        from axm_init.core.templates import TemplateInfo

        mock_resolve.return_value = TemplateInfo(
            name="minimal",
            path=str(tmp_path),
            description="Minimal template",
        )
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": [], "message": "ok"}
        )()

        f = io.StringIO()
        try:
            with redirect_stdout(f):
                app(
                    ["init", str(tmp_path), "--name", "test-project"],
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
