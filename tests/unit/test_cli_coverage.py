"""Tests for CLI coverage gaps — reserve JSON success, init failure output."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_init.cli import app
from axm_init.core.reserver import ReserveResult


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
        code = 1
    return out.getvalue(), err.getvalue(), code


INIT_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]


class TestReserveJsonSuccess:
    """Cover reserve command JSON output for success path."""

    @patch("axm_init.cli.reserve_pypi")
    @patch("axm_init.cli.CredentialManager")
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
        stdout, _, code = _run(["reserve", "test-pkg", "--dry-run", "--json"])
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True

    @patch("axm_init.cli.reserve_pypi")
    @patch("axm_init.cli.CredentialManager")
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
        stdout, _, code = _run(["reserve", "taken-pkg", "--dry-run", "--json"])
        # JSON mode always prints and exits 0 (no SystemExit in json branch)
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is False

    @patch("axm_init.cli.reserve_pypi")
    @patch("axm_init.cli.CredentialManager")
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
        _, stderr, code = _run(["reserve", "taken-pkg", "--dry-run"])
        assert code == 1
        assert "❌" in stderr


class TestInitFailurePath:
    """Cover init command failure output (copier fails)."""

    @patch("axm_init.cli.CopierAdapter")
    def test_init_copier_fails_human(
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
            ["init", str(tmp_path), "--name", "fail-pkg", *INIT_ARGS]
        )
        assert code == 1
        assert "❌" in stderr

    @patch("axm_init.cli.CopierAdapter")
    def test_init_json_success(
        self, mock_copier_cls: MagicMock, tmp_path: Path
    ) -> None:
        """--json with successful init outputs JSON with success=true."""
        mock_adapter = mock_copier_cls.return_value
        mock_adapter.copy.return_value = type(
            "R", (), {"success": True, "files_created": ["a.py"], "message": "ok"}
        )()
        stdout, _, code = _run(
            ["init", str(tmp_path), "--name", "my-pkg", "--json", *INIT_ARGS]
        )
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True


class TestInitPyPIJsonError:
    """Cover --check-pypi + --json error path (status=ERROR)."""

    @patch("axm_init.cli.CopierAdapter")
    @patch("axm_init.cli.PyPIAdapter")
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
            [
                "init",
                str(tmp_path),
                "--name",
                "pkg",
                "--check-pypi",
                "--json",
                *INIT_ARGS,
            ]
        )
        assert code == 0
