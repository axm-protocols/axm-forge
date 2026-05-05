"""Unit tests for run_in_project helpers and rule subprocess wiring (mocked, no I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


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
        """DependencyAuditRule passes with_packages=["pip-audit"]."""
        from axm_audit.core.rules.dependencies import DependencyAuditRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            DependencyAuditRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["pip-audit"]

    def test_deptry_injects_deptry(self, tmp_path: Path) -> None:
        """DependencyHygieneRule passes with_packages=["deptry"]."""
        from axm_audit.core.rules.dependencies import DependencyHygieneRule

        with patch("axm_audit.core.rules.dependencies.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            DependencyHygieneRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["deptry"]
