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

    def test_with_packages_inserts_flags(self, tmp_path: Path) -> None:
        """with_packages adds --with flags between 'uv run' and '--directory'."""
        from axm_audit.core.runner import run_in_project

        # Create a fake .venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(
                ["pytest", "--json-report"],
                tmp_path,
                with_packages=["pytest-json-report", "pytest-cov"],
            )

            args = mock_run.call_args[0][0]
            assert args == [
                "uv",
                "run",
                "--with",
                "pytest-json-report",
                "--with",
                "pytest-cov",
                "--directory",
                str(tmp_path),
                "pytest",
                "--json-report",
            ]

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

    def test_with_packages_none_no_effect(self, tmp_path: Path) -> None:
        """with_packages=None produces same command as before."""
        from axm_audit.core.runner import run_in_project

        # Create a fake .venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check"], tmp_path, with_packages=None)

            args = mock_run.call_args[0][0]
            assert args == ["uv", "run", "--directory", str(tmp_path), "ruff", "check"]


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

    def test_coverage_uses_run_tests(self, tmp_path: Path) -> None:
        """TestCoverageRule should delegate to run_tests."""
        from axm_audit.core.rules.coverage import TestCoverageRule
        from axm_audit.core.test_runner import TestReport

        mock_report = TestReport(passed=42, failed=0, duration=5.0, coverage=95.0)
        with patch(
            "axm_audit.core.test_runner.run_tests", return_value=mock_report
        ) as mock:
            TestCoverageRule().check(tmp_path)
            mock.assert_called_once()

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


# ── Tests for with_packages injection in rules ──────────────────────


class TestWithPackagesInjection:
    """Verify each rule passes the correct with_packages to run_in_project."""

    def test_linting_injects_ruff(self, tmp_path: Path) -> None:
        """LintingRule passes with_packages=["ruff"]."""
        from axm_audit.core.rules.quality import LintingRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
            LintingRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["ruff"]

    def test_formatting_injects_ruff(self, tmp_path: Path) -> None:
        """FormattingRule passes with_packages=["ruff"]."""
        from axm_audit.core.rules.quality import FormattingRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
            FormattingRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["ruff"]

    def test_typecheck_injects_mypy(self, tmp_path: Path) -> None:
        """TypeCheckRule passes with_packages=["mypy"]."""
        from axm_audit.core.rules.quality import TypeCheckRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
            TypeCheckRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["mypy"]

    def test_security_injects_bandit(self, tmp_path: Path) -> None:
        """SecurityRule passes with_packages=["bandit"]."""
        from axm_audit.core.rules.security import SecurityRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.security.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            SecurityRule().check(tmp_path)
            assert mock.call_args[1]["with_packages"] == ["bandit"]

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

    def test_run_tests_injects_pytest_plugins(self, tmp_path: Path) -> None:
        """run_tests passes with_packages=["pytest-json-report", "pytest-cov"]."""
        import json

        from axm_audit.core.test_runner import run_tests

        passing_report = {
            "summary": {
                "passed": 1,
                "failed": 0,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
                "duration": 0.1,
            },
            "tests": [],
        }
        coverage_data = {
            "totals": {"percent_covered": 90.0},
            "files": {},
        }

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: object
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    Path(arg.split("=", 1)[1]).write_text(json.dumps(passing_report))
                if arg.startswith("--cov-report=json:"):
                    Path(arg.split(":", 1)[1]).write_text(json.dumps(coverage_data))
            return MagicMock(returncode=0)

        with patch("axm_audit.core.test_runner.run_in_project") as mock:
            mock.side_effect = _side_effect
            run_tests(tmp_path, mode="compact")
            assert mock.call_args[1]["with_packages"] == [
                "pytest-json-report",
                "pytest-cov",
            ]
