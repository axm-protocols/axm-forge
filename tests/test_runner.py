"""Tests for run_in_project helper and rule subprocess integration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Tests for run_in_project helper ──────────────────────────────────


class TestRunInProject:
    """Tests for the run_in_project subprocess helper."""

    def test_with_venv_uses_uv_run(self, tmp_path: Path) -> None:
        """When .venv exists, should prefix cmd with uv run --directory."""
        from axm_audit.core.runner import run_in_project

        # Create a fake .venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check", "src"], tmp_path)

            args = mock_run.call_args[0][0]
            assert args[:4] == ["uv", "run", "--directory", str(tmp_path)]
            assert args[4:] == ["ruff", "check", "src"]

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


# ── Tests for rule integration ───────────────────────────────────────


class TestRulesUseRunInProject:
    """Verify all rules use run_in_project instead of direct subprocess."""

    def test_linting_uses_run_in_project(self, tmp_path: Path) -> None:
        """LintingRule should call run_in_project."""
        from axm_audit.core.rules.quality import LintingRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            LintingRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "ruff"

    def test_typecheck_uses_run_in_project(self, tmp_path: Path) -> None:
        """TypeCheckRule should call run_in_project."""
        from axm_audit.core.rules.quality import TypeCheckRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
            TypeCheckRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "mypy"

    def test_coverage_uses_run_in_project(self, tmp_path: Path) -> None:
        """TestCoverageRule should call run_in_project."""
        from axm_audit.core.rules.quality import TestCoverageRule

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
            TestCoverageRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "pytest"

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

    def test_bandit_uses_run_in_project(self, tmp_path: Path) -> None:
        """SecurityRule should call run_in_project."""
        from axm_audit.core.rules.security import SecurityRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.security.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            SecurityRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "bandit"


# ── Grep test: no sys.executable in rules ────────────────────────────


class TestNoSysExecutable:
    """Ensure sys.executable is not used in any rule files."""

    def test_no_sys_executable_in_rules(self) -> None:
        """Rule files should not reference sys.executable."""
        rules_dir = Path("src/axm_audit/core/rules")
        for py_file in rules_dir.glob("*.py"):
            content = py_file.read_text()
            assert "sys.executable" not in content, (
                f"{py_file.name} still uses sys.executable"
            )
