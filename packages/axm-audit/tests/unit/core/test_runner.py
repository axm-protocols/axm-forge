"""Unit tests for run_in_project helpers and rule subprocess wiring (mocked, no I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRunInProjectUnit:
    """Unit tests for run_in_project (mocked subprocess, no real I/O)."""

    def test_without_venv_falls_back_to_bare_cmd(self, tmp_path: Path) -> None:
        """When no .venv exists, should run cmd directly with cwd."""
        from axm_audit.core.runner import run_in_project

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check", "src"], tmp_path)

            args = mock_run.call_args[0][0]
            assert args == ["ruff", "check", "src"]
            assert mock_run.call_args[1]["cwd"] == str(tmp_path)

    def test_passes_kwargs(self, tmp_path: Path) -> None:
        """Extra kwargs should be forwarded to subprocess.run."""
        from axm_audit.core.runner import run_in_project

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check"], tmp_path, capture_output=True, text=True)

            kwargs = mock_run.call_args[1]
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True

    def test_run_in_project_timeout(self, tmp_path: Path) -> None:
        """TimeoutExpired is caught and results in a clear error."""
        from axm_audit.core.runner import run_in_project

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["ruff", "check"], timeout=10
            )
            result = run_in_project(["ruff", "check"], tmp_path, timeout=10)

            assert result.returncode == 124
            assert "timed out after 10s" in result.stderr
            assert result.stdout == ""

    def test_run_in_project_default_timeout(self, tmp_path: Path) -> None:
        """Default timeout of 300s is passed to subprocess.run."""
        from axm_audit.core.runner import run_in_project

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check"], tmp_path)

            kwargs = mock_run.call_args[1]
            assert kwargs["timeout"] == 300

    def test_with_packages_ignored_without_venv(self, tmp_path: Path) -> None:
        """with_packages has no effect when no .venv exists (bare cmd)."""
        from axm_audit.core.runner import run_in_project

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(
                ["pytest", "--json-report"],
                tmp_path,
                with_packages=["pytest-json-report"],
            )

            args = mock_run.call_args[0][0]
            assert args == ["pytest", "--json-report"]
            assert "--with" not in args


class TestRulesUseRunInProjectUnit:
    """Unit: dependency rules use run_in_project (no real src/ dir)."""

    def test_pip_audit_uses_run_in_project(self, tmp_path: Path) -> None:
        """DependencyAuditRule should call run_in_project."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            DependencyAuditRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "pip-audit"

    def test_deptry_uses_run_in_project(self, tmp_path: Path) -> None:
        """DependencyHygieneRule should call run_in_project."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            DependencyHygieneRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "deptry"


class TestWithPackagesInjectionUnit:
    """Unit: dependency rules inject with_packages (no real src/ dir)."""

    def test_pip_audit_injects_pip_audit(self, tmp_path: Path) -> None:
        """DependencyAuditRule passes with_packages=[\"pip-audit\"]."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            DependencyAuditRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["pip-audit"]

    def test_deptry_injects_deptry(self, tmp_path: Path) -> None:
        """DependencyHygieneRule passes with_packages=[\"deptry\"]."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            DependencyHygieneRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["deptry"]


# --- find_venv: public surface (AC3) ---


def test_find_venv_public() -> None:
    """find_venv is importable as a public callable."""
    from axm_audit.core.runner import find_venv

    assert callable(find_venv)


def test_find_venv_private_alias_removed() -> None:
    """_find_venv shim is gone from core.runner."""
    from axm_audit.core import runner

    assert not hasattr(runner, "_find_venv"), (
        "deprecated private alias _find_venv still exposed"
    )


# --- run_tests timeout handling (AXM-1800) ---
#
# These exercise the public ``run_tests`` entry point with
# ``run_in_project`` mocked at the test_runner boundary (module-level
# import), distinct from the run_in_project-layer tests above.

_DEAD_PROJECT = Path("/nonexistent/project")


def test_run_tests_timeout_does_not_report_partial_coverage() -> None:
    """AC1: a timed-out subprocess (returncode 124) must not yield a
    coverage percentage parsed from partial JSON; coverage is unmeasured.
    """
    from axm_audit.core.test_runner import run_tests

    timed_out = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=124,
        stdout="",
        stderr="Command timed out after 900s",
    )
    with (
        patch("axm_audit.core.test_runner.run_in_project", return_value=timed_out),
        patch(
            "axm_audit.core.test_runner.parse_coverage",
            return_value=(88.0, {"a.py": 88.0}),
        ) as parse_cov,
    ):
        report = run_tests(_DEAD_PROJECT)

    # Coverage must NOT be fabricated from partial data.
    assert report.coverage is None
    # The timeout must be surfaced explicitly on the report.
    assert getattr(report, "timed_out", False) is True
    # parse_coverage must not be consulted for a percentage after a timeout.
    parse_cov.assert_not_called()


def test_run_tests_passes_explicit_timeout() -> None:
    """AC3: ``run_tests`` passes an explicit elevated ``timeout`` to
    ``run_in_project`` for the coverage run (>= 900s), not the implicit 300.
    """
    from axm_audit.core.test_runner import run_tests

    ok = subprocess.CompletedProcess(
        args=["pytest"], returncode=0, stdout="", stderr=""
    )
    with (
        patch(
            "axm_audit.core.test_runner.run_in_project", return_value=ok
        ) as run_in_project,
        patch("axm_audit.core.test_runner.parse_json_report", return_value={}),
        patch(
            "axm_audit.core.test_runner.parse_coverage",
            return_value=(90.0, {}),
        ),
    ):
        run_tests(_DEAD_PROJECT)

    assert run_in_project.call_args.kwargs.get("timeout", 300) >= 900


def test_run_tests_normal_run_unaffected() -> None:
    """AC4: a non-timeout run (returncode 0) parses and reports coverage
    exactly as before — regression guard for the happy path.
    """
    from axm_audit.core.test_runner import run_tests

    ok = subprocess.CompletedProcess(
        args=["pytest"], returncode=0, stdout="", stderr=""
    )
    with (
        patch("axm_audit.core.test_runner.run_in_project", return_value=ok),
        patch(
            "axm_audit.core.test_runner.parse_json_report",
            return_value={"summary": {"passed": 3}, "tests": []},
        ),
        patch(
            "axm_audit.core.test_runner.parse_coverage",
            return_value=(90.0, {"a.py": 90.0}),
        ),
    ):
        report = run_tests(_DEAD_PROJECT)

    assert report.coverage == 90.0
    assert getattr(report, "timed_out", False) is False
    assert report.passed == 3


# --- interpret_process classifier + check semantics (AXM-1958) ---


def test_interpret_process_classifies_clean_issues_env_failure() -> None:
    """AC2: rc=0 -> CLEAN, rc=1+findings -> ISSUES, rc in {2,124} -> ENV_FAILURE."""
    from axm_audit.core.runner import ProcessVerdict, interpret_process

    clean = subprocess.CompletedProcess(args=["x"], returncode=0, stdout="")
    issues = subprocess.CompletedProcess(
        args=["x"], returncode=1, stdout='[{"code": "E501"}]'
    )
    timeout = subprocess.CompletedProcess(args=["x"], returncode=124, stdout="")
    blocking = subprocess.CompletedProcess(args=["x"], returncode=2, stdout="")

    assert interpret_process(clean) is ProcessVerdict.CLEAN
    assert interpret_process(issues) is ProcessVerdict.ISSUES
    assert interpret_process(timeout) is ProcessVerdict.ENV_FAILURE
    assert interpret_process(blocking) is ProcessVerdict.ENV_FAILURE


def test_run_in_project_check_true_raises_on_timeout(tmp_path: Path) -> None:
    """AC3: check=True on a timeout raises instead of returning rc=124."""
    from axm_audit.core.runner import run_in_project

    with patch("axm_audit.core.runner.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ruff"], timeout=1)
        with pytest.raises(subprocess.TimeoutExpired):
            run_in_project(["ruff"], tmp_path, check=True)


def test_run_in_project_check_false_returns_synthetic_on_timeout(
    tmp_path: Path,
) -> None:
    """AC3: check=False on a timeout keeps the synthetic rc=124 result."""
    from axm_audit.core.runner import run_in_project

    with patch("axm_audit.core.runner.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ruff"], timeout=1)
        result = run_in_project(["ruff"], tmp_path, check=False)
    assert result.returncode == 124
