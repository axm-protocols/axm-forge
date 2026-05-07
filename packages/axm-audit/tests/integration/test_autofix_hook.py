"""Tests for AutofixHook — ruff fix + format before gate evaluation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_audit.hooks.autofix import AutofixHook


@pytest.fixture
def hook() -> AutofixHook:
    """Create an AutofixHook instance."""
    return AutofixHook()


@pytest.fixture
def context(tmp_path: Path) -> dict[str, str]:
    """Minimal hook context with a working directory."""
    return {"working_dir": str(tmp_path)}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestAutofixRunsRuffFix:
    """AutofixHook invokes ruff check --fix."""

    def test_autofix_runs_ruff_fix(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        mock_run = mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )
        hook.execute(context)

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert ["ruff", "check", "--fix", "."] in calls


class TestAutofixRunsRuffFormat:
    """AutofixHook invokes ruff format."""

    def test_autofix_runs_ruff_format(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        mock_run = mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )
        hook.execute(context)

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert ["ruff", "format", "."] in calls


class TestAutofixSkipsNoRuff:
    """AutofixHook skips gracefully when ruff is not installed."""

    def test_autofix_skips_no_ruff(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            side_effect=FileNotFoundError("ruff not found"),
        )
        result = hook.execute(context)

        assert result.success is True
        assert result.metadata.get("skipped") is True


class TestAutofixReportsFixes:
    """AutofixHook reports number of fixes applied."""

    def test_autofix_reports_fixes(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        ruff_fix_output = "Found 4 errors (2 fixed, 2 remaining)."
        mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=ruff_fix_output,
                stderr="",
            ),
        )
        result = hook.execute(context)

        assert result.success is True
        assert result.metadata.get("fixed") == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestAutofixNoPythonFiles:
    """AutofixHook succeeds on empty project with 0 fixes."""

    def test_no_python_files(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )
        result = hook.execute(context)

        assert result.success is True
        assert result.metadata.get("fixed", 0) == 0


class TestAutofixRuffConfigError:
    """AutofixHook handles invalid pyproject.toml gracefully."""

    def test_ruff_config_error(
        self,
        hook: AutofixHook,
        context: dict[str, str],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "axm_audit.hooks.autofix.run_in_project",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=2,
                stdout="",
                stderr="error: Failed to parse pyproject.toml",
            ),
        )
        result = hook.execute(context)

        assert result.success is True
