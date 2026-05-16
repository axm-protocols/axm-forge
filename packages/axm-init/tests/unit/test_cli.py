"""Unit tests for CLI — mirror of src/axm_init/cli.py.

Covers:
- app identity and command registration
- version command
- check command (non-I/O edge cases + self-test)
- scaffold command (help text + workspace/member flags)
- reserve command (JSON output, validation, edge cases)
- help display
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import cyclopts
import pytest

from axm_init.cli import app
from axm_init.models.results import ReserveResult


def _run_simple(args: list[str]) -> tuple[str, int]:
    """Run CLI and capture stdout + exit code."""
    f = io.StringIO()
    code = 0
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return f.getvalue(), code


def _run(*args: str) -> tuple[str, str, int]:
    """Run CLI and capture stdout/stderr/exit_code."""
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
        assert command_name in self._command_names()


class TestVersionFlow:
    """End-to-end test for version command."""

    def test_version_returns_valid_output(self) -> None:
        """version command produces clean output matching 'axm-init X.Y.Z'."""
        output, code = _run_simple(["version"])
        assert code == 0
        output = output.strip()
        assert output.startswith("axm-init ")
        assert "Error" not in output
        assert "Traceback" not in output
        parts = output.split()
        assert len(parts) == 2
        assert parts[0] == "axm-init"


class TestCheckCommandUnit:
    """Tests for `axm-init check` — non-I/O edge cases."""

    def test_nonexistent_path(self) -> None:
        _stdout, stderr, code = _run("check", "/tmp/nonexistent_axm_path")
        assert code == 1
        assert "Not a directory" in stderr


class TestCheckSelfTest:
    """axm-init itself should score >= B."""

    def test_self_audit(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        stdout, _stderr, _code = _run("check", str(project_root), "--json")
        data = json.loads(stdout)
        assert data["score"] >= 75, f"Self-check score too low: {data['score']}"
        assert data["grade"] in ("A", "B")


class TestScaffoldCommandOptions:
    """Tests for scaffold command help text (no real I/O)."""

    def _capture_help(self) -> str:
        stdout, _, _ = _run("scaffold", "--help")
        return stdout

    def test_scaffold_help_does_not_crash(self) -> None:
        output = self._capture_help()
        assert "scaffold" in output.lower() or "path" in output.lower()

    def test_scaffold_help_shows_org_flag(self) -> None:
        assert "--org" in self._capture_help()

    def test_scaffold_help_shows_author_flag(self) -> None:
        assert "--author" in self._capture_help()

    def test_scaffold_help_shows_email_flag(self) -> None:
        assert "--email" in self._capture_help()

    def test_scaffold_help_no_template_flag(self) -> None:
        """scaffold --help must NOT show --template flag (removed)."""
        assert "--template" not in self._capture_help()


class TestReserveJsonOutput:
    """Cover reserve command JSON output for success and failure paths."""

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


class TestReserveCommandEdgeCases:
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
    """Test that --help shows registered commands."""

    def test_help_shows_commands(self) -> None:
        """--help shows all registered commands."""
        stdout, _, _ = _run("--help")
        assert "scaffold" in stdout
        assert "reserve" in stdout
        assert "version" in stdout


# --- workspace scaffold flags ---


class TestCliScaffoldTemplateRouting:
    """AC1/AC4: --workspace flag routes to correct template."""

    @pytest.mark.parametrize(
        ("name", "workspace", "expected_in_path"),
        [
            pytest.param("test-ws", True, "workspace", id="workspace_flag"),
            pytest.param(
                "test-project", False, "python-project", id="default_standalone"
            ),
        ],
    )
    def test_cli_scaffold_template_routing(
        self,
        tmp_path: Path,
        name: str,
        workspace: bool,
        expected_in_path: str,
    ) -> None:
        """scaffold routes to workspace or standalone template based on flag."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            kwargs: dict[str, object] = {
                "name": name,
                "org": "test-org",
                "author": "Test",
                "email": "test@test.com",
            }
            if workspace:
                kwargs["workspace"] = True
            scaffold(str(tmp_path), **kwargs)

        call_args = mock_copier.copy.call_args[0][0]
        assert expected_in_path in str(call_args.template_path).lower()


class TestCliScaffoldMutualExclusive:
    """AC3: --workspace and --member are mutually exclusive."""

    def test_cli_scaffold_mutual_exclusive(self, tmp_path: Path) -> None:
        """Error when both --workspace and --member are given."""
        from axm_init.cli import scaffold

        with pytest.raises(SystemExit, match="1"):
            scaffold(
                str(tmp_path),
                org="test-org",
                author="Test",
                email="test@test.com",
                workspace=True,
                member="foo",
            )


class TestCliMemberOutsideWorkspace:
    """AC6: --member outside workspace prints error."""

    def test_cli_member_outside_workspace(self, tmp_path: Path) -> None:
        """Running --member without a workspace exits with error."""
        from axm_init.cli import scaffold

        with pytest.raises(SystemExit, match="1"):
            scaffold(
                str(tmp_path),
                org="test-org",
                author="Test",
                email="test@test.com",
                member="my-pkg",
            )
