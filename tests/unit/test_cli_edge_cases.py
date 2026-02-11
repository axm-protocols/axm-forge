"""Unit tests for CLI commands — edge cases and error paths."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from axm_init.cli import app

runner = CliRunner()


class TestVersionCommand:
    """Tests for the version command."""

    def test_version_output_contains_name(self) -> None:
        """Output contains 'axm-init'."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "axm-init" in result.stdout

    def test_version_output_format(self) -> None:
        """Output matches 'axm-init X.Y.Z' pattern."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        parts = result.stdout.strip().split()
        assert len(parts) == 2
        assert parts[0] == "axm-init"


class TestInitCommand:
    """Tests for the init command — edge cases."""

    def test_init_no_name_defaults_to_dirname(self, tmp_path) -> None:
        """When --name is omitted, project name defaults to directory name."""
        target = tmp_path / "my-awesome-project"
        target.mkdir()
        result = runner.invoke(app, ["init", str(target)])
        assert result.exit_code == 0
        assert "my-awesome-project" in result.stdout

    def test_init_invalid_template_exits_with_error(self, tmp_path) -> None:
        """Unknown template name causes exit code 1."""
        result = runner.invoke(
            app, ["init", str(tmp_path), "--template", "nonexistent"]
        )
        assert result.exit_code == 1
        assert "Unknown template" in result.output

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_taken_exits_with_error(self, mock_cls, tmp_path) -> None:
        """--check-pypi with taken name causes exit code 1."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

        result = runner.invoke(
            app,
            ["init", str(tmp_path), "--name", "requests", "--check-pypi"],
        )
        assert result.exit_code == 1

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_taken_json_output(self, mock_cls, tmp_path) -> None:
        """--check-pypi + --json outputs JSON error for taken name."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

        result = runner.invoke(
            app,
            [
                "init",
                str(tmp_path),
                "--name",
                "requests",
                "--check-pypi",
                "--json",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_error_continues(self, mock_cls, tmp_path) -> None:
        """--check-pypi with network error continues (warning only)."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.ERROR

        result = runner.invoke(
            app,
            ["init", str(tmp_path), "--name", "test-pkg", "--check-pypi"],
        )
        # Should not fail — availability check error is non-blocking
        assert result.exit_code == 0


class TestReserveCommand:
    """Tests for the reserve command — edge cases."""

    @patch("axm_init.cli.CredentialManager")
    def test_reserve_no_token_json_exits(self, mock_cls) -> None:
        """No token + --json outputs error JSON and exits 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        result = runner.invoke(
            app,
            ["reserve", "test-pkg", "--json"],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    @patch("axm_init.cli.CredentialManager")
    def test_reserve_resolve_fails_exits(self, mock_cls) -> None:
        """resolve_pypi_token raising SystemExit causes CLI exit 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        result = runner.invoke(
            app,
            ["reserve", "test-pkg"],
        )
        assert result.exit_code == 1

    @patch("axm_init.cli.reserve_pypi")
    @patch("axm_init.cli.CredentialManager")
    def test_reserve_dry_run_succeeds(self, mock_cred_cls, mock_reserve) -> None:
        """--dry-run skips resolve_pypi_token and succeeds."""
        from axm_init.core.reserver import ReserveResult

        mock_creds = mock_cred_cls.return_value
        mock_creds.get_pypi_token.return_value = None

        mock_reserve.return_value = ReserveResult(
            success=True,
            package_name="test-pkg",
            version="0.0.1.dev0",
            message="Dry run — would reserve 'test-pkg' on PyPI",
        )

        result = runner.invoke(app, ["reserve", "test-pkg", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        # resolve_pypi_token should NOT be called in dry-run
        mock_creds.resolve_pypi_token.assert_not_called()


class TestNoArgsShowsHelp:
    """Test that running without arguments shows help."""

    def test_no_args_shows_help(self) -> None:
        """Running with no arguments shows help text."""
        result = runner.invoke(app, [])
        # Typer's no_args_is_help exits with code 2
        assert result.exit_code == 2
        assert "init" in result.output
