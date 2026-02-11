"""Unit tests for CLI commands — edge cases and error paths."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from axm_init.cli import app


def _run(args: list[str]) -> tuple[str, str, int]:
    """Run CLI, capture stdout + stderr + exit code."""
    out = io.StringIO()
    err = io.StringIO()
    code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            app(args, exit_on_error=False)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception:
        # Cyclopts raises MissingArgumentError etc. when exit_on_error=False
        code = 1
    return out.getvalue(), err.getvalue(), code


# Required args for init (to avoid noise in unrelated tests)
INIT_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]


class TestVersionCommand:
    """Tests for the version command."""

    def test_version_output_contains_name(self) -> None:
        """Output contains 'axm-init'."""
        stdout, _, code = _run(["version"])
        assert code == 0
        assert "axm-init" in stdout

    def test_version_output_format(self) -> None:
        """Output matches 'axm-init X.Y.Z' pattern."""
        stdout, _, code = _run(["version"])
        assert code == 0
        parts = stdout.strip().split()
        assert len(parts) == 2
        assert parts[0] == "axm-init"


class TestInitCommand:
    """Tests for the init command — edge cases."""

    def test_init_no_name_defaults_to_dirname(self, tmp_path) -> None:
        """When --name is omitted, project name defaults to directory name."""
        target = tmp_path / "my-awesome-project"
        target.mkdir()
        stdout, _, code = _run(["init", str(target), *INIT_ARGS])
        assert code == 0
        assert "my-awesome-project" in stdout

    def test_init_missing_org_exits(self, tmp_path) -> None:
        """Missing --org causes exit with error."""
        _, _, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "x",
                "--author",
                "A",
                "--email",
                "e@e.com",
            ]
        )
        assert code != 0

    def test_init_missing_author_exits(self, tmp_path) -> None:
        """Missing --author causes exit with error."""
        _, _, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "x",
                "--org",
                "o",
                "--email",
                "e@e.com",
            ]
        )
        assert code != 0

    def test_init_missing_email_exits(self, tmp_path) -> None:
        """Missing --email causes exit with error."""
        _, _, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "x",
                "--org",
                "o",
                "--author",
                "A",
            ]
        )
        assert code != 0

    @patch("axm_init.cli.CopierAdapter")
    def test_init_license_holder_defaults_to_org(
        self, mock_copier_cls, tmp_path
    ) -> None:
        """When --license-holder is omitted, it defaults to --org value."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": [], "message": "ok"}
        )()

        _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "test-pkg",
                "--org",
                "my-org",
                "--author",
                "A",
                "--email",
                "e@e.com",
            ]
        )

        # Check that CopierConfig was created with license_holder = org
        call_args = mock_copier_cls.return_value.copy.call_args
        config = call_args[0][0]
        assert config.data["license_holder"] == "my-org"

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_taken_exits_with_error(self, mock_cls, tmp_path) -> None:
        """--check-pypi with taken name causes exit code 1."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

        _, _stderr, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "requests",
                "--check-pypi",
                *INIT_ARGS,
            ]
        )
        assert code == 1

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_taken_json_output(self, mock_cls, tmp_path) -> None:
        """--check-pypi + --json outputs JSON error for taken name."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.TAKEN

        stdout, _, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "requests",
                "--check-pypi",
                "--json",
                *INIT_ARGS,
            ]
        )
        assert code == 1
        data = json.loads(stdout)
        assert "error" in data

    @patch("axm_init.cli.PyPIAdapter")
    def test_init_pypi_error_continues(self, mock_cls, tmp_path) -> None:
        """--check-pypi with network error continues (warning only)."""
        from axm_init.adapters.pypi import AvailabilityStatus

        mock_adapter = mock_cls.return_value
        mock_adapter.check_availability.return_value = AvailabilityStatus.ERROR

        _, _, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "test-pkg",
                "--check-pypi",
                *INIT_ARGS,
            ]
        )
        # Should not fail — availability check error is non-blocking
        assert code == 0


class TestReserveCommand:
    """Tests for the reserve command — edge cases."""

    @patch("axm_init.cli.CredentialManager")
    def test_reserve_no_token_json_exits(self, mock_cls) -> None:
        """No token + --json outputs error JSON and exits 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        stdout, _, code = _run(["reserve", "test-pkg", "--json"])
        assert code == 1
        data = json.loads(stdout)
        assert "error" in data

    @patch("axm_init.cli.CredentialManager")
    def test_reserve_resolve_fails_exits(self, mock_cls) -> None:
        """resolve_pypi_token raising SystemExit causes CLI exit 1."""
        mock_creds = mock_cls.return_value
        mock_creds.resolve_pypi_token.side_effect = SystemExit(1)

        _, _, code = _run(["reserve", "test-pkg"])
        assert code == 1

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

        stdout, _, code = _run(["reserve", "test-pkg", "--dry-run"])
        assert code == 0
        assert "Dry run" in stdout
        # resolve_pypi_token should NOT be called in dry-run
        mock_creds.resolve_pypi_token.assert_not_called()


class TestHelpBehavior:
    """Test help display behavior."""

    def test_no_args_shows_help(self) -> None:
        """Running with no arguments shows help text."""
        stdout, _, _code = _run(["--help"])
        assert "init" in stdout
