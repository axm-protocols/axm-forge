"""Unit tests for CLI — mirror of src/axm_init/cli.py.

Covers:
- version command (TestVersionFlow)
- check command end-to-end (TestCheckSelfTest)
- scaffold workspace/member flags (TestCliScaffold*)
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.cli import app


def _run(args: list[str]) -> tuple[str, int]:
    """Run CLI and capture stdout + exit code."""
    f = io.StringIO()
    code = 0
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return f.getvalue(), code


class TestVersionFlow:
    """End-to-end test for version command."""

    def test_version_returns_valid_output(self) -> None:
        """version command produces clean output."""
        output, code = _run(["version"])
        assert code == 0
        output = output.strip()
        assert output.startswith("axm-init ")
        # Should not contain error messages
        assert "Error" not in output
        assert "Traceback" not in output


# --- check CLI command ---


def _run_check(*args: str) -> tuple[str, str, int]:
    """Run CLI command and capture stdout/stderr/exit_code."""
    out, err = io.StringIO(), io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            app(args)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    return out.getvalue(), err.getvalue(), exit_code


class TestCheckSelfTest:
    """axm-init itself should score >= B."""

    def test_self_audit(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        stdout, _stderr, _code = _run_check("check", str(project_root), "--json")
        data = json.loads(stdout)
        assert data["score"] >= 75, f"Self-check score too low: {data['score']}"
        assert data["grade"] in ("A", "B")


# --- workspace scaffold flags ---


class TestCliScaffoldWorkspace:
    """AC1: --workspace invokes workspace scaffold."""

    def test_cli_scaffold_workspace(self, tmp_path: Path) -> None:
        """scaffold --workspace routes to workspace template."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(tmp_path),
                name="test-ws",
                org="test-org",
                author="Test",
                email="test@test.com",
                workspace=True,
            )

        call_args = mock_copier.copy.call_args[0][0]
        assert "workspace" in str(call_args.template_path).lower()


class TestCliScaffoldDefaultUnchanged:
    """AC4: Default scaffold (no flags) uses standalone template."""

    def test_cli_scaffold_default_unchanged(self, tmp_path: Path) -> None:
        """Default scaffold produces standalone package."""
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [tmp_path / "pyproject.toml"]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(tmp_path),
                name="test-project",
                org="test-org",
                author="Test",
                email="test@test.com",
            )

        call_args = mock_copier.copy.call_args[0][0]
        assert "python-project" in str(call_args.template_path).lower()


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
