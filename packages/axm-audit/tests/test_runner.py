"""Tests for run_in_project helper and rule subprocess integration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Tests for _find_venv helper ──────────────────────────────────────


class TestFindVenv:
    """Tests for the _find_venv workspace-aware venv locator."""

    def test_finds_local_venv(self, tmp_path: Path) -> None:
        """Returns .venv when present directly in project_path."""
        from axm_audit.core.runner import _find_venv

        (tmp_path / "pyproject.toml").touch()
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        result = _find_venv(tmp_path)
        assert result == tmp_path / ".venv"

    def test_finds_workspace_root_venv(self, tmp_path: Path) -> None:
        """Returns workspace-root .venv when subpackage has no local .venv."""
        from axm_audit.core.runner import _find_venv

        # Simulate: workspace_root/pyproject.toml + .venv
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / "pyproject.toml").touch()
        venv_bin = workspace_root / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        # Subpackage is a DIRECT child (uv workspace members are flat siblings)
        subpackage = workspace_root / "my-lib"
        subpackage.mkdir()
        (subpackage / "pyproject.toml").touch()

        result = _find_venv(subpackage)
        assert result == workspace_root / ".venv"

    def test_returns_none_when_no_venv(self, tmp_path: Path) -> None:
        """Returns None when no .venv exists anywhere in the project tree."""
        from axm_audit.core.runner import _find_venv

        (tmp_path / "pyproject.toml").touch()
        # No .venv created

        result = _find_venv(tmp_path)
        assert result is None

    def test_find_venv_packages_layout(self, tmp_path: Path) -> None:
        """Finds workspace-root .venv through intermediate dir without pyproject.toml.

        Regression test for AXM-300: _find_venv stopped at intermediate
        directories (e.g. ``packages/``) that lack a ``pyproject.toml``,
        never reaching the workspace root where ``.venv`` lives.
        """
        from axm_audit.core.runner import _find_venv

        # workspace/
        # ├── .venv/bin/python
        # ├── pyproject.toml
        # └── packages/          ← no pyproject.toml
        #     └── my-pkg/
        #         └── pyproject.toml
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "pyproject.toml").touch()
        venv_bin = workspace / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        packages = workspace / "packages"
        packages.mkdir()
        # No pyproject.toml in packages/

        pkg = packages / "my-pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").touch()

        result = _find_venv(pkg)
        assert result == workspace / ".venv"

    def test_find_venv_flat_workspace(self, tmp_path: Path) -> None:
        """Finds workspace-root .venv in flat workspace layout (no packages/ dir)."""
        from axm_audit.core.runner import _find_venv

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "pyproject.toml").touch()
        venv_bin = workspace / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        pkg = workspace / "my-lib"
        pkg.mkdir()
        (pkg / "pyproject.toml").touch()

        result = _find_venv(pkg)
        assert result == workspace / ".venv"

    def test_find_venv_bounded_depth(self, tmp_path: Path) -> None:
        """Returns None when .venv is beyond _MAX_VENV_SEARCH_DEPTH levels up."""
        from axm_audit.core.runner import _MAX_VENV_SEARCH_DEPTH, _find_venv

        # Create a .venv at the top, then nest deeper than the limit
        top = tmp_path / "top"
        top.mkdir()
        venv_bin = top / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        # Build a path _MAX_VENV_SEARCH_DEPTH levels deep (beyond the limit)
        deep = top
        for i in range(_MAX_VENV_SEARCH_DEPTH):
            deep = deep / f"level{i}"
            deep.mkdir()

        result = _find_venv(deep)
        assert result is None


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
        (tmp_path / "pyproject.toml").touch()

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["ruff", "check", "src"], tmp_path)

            args = mock_run.call_args[0][0]
            assert args[:4] == ["uv", "run", "--directory", str(tmp_path)]
            assert args[4:] == ["ruff", "check", "src"]

    def test_workspace_subpackage_uses_uv_run(self, tmp_path: Path) -> None:
        """Workspace member uses uv run when .venv is at monorepo root.

        Regression test for AXM-290: audit_test returned 0 tests for
        workspace subpackages because run_in_project only checked for
        .venv in project_path directly, missing workspace-root venvs.
        """
        from axm_audit.core.runner import run_in_project

        # Simulate uv monorepo: root has .venv, subpackage does not
        workspace_root = tmp_path / "axm-protocols"
        workspace_root.mkdir()
        (workspace_root / "pyproject.toml").touch()
        venv_bin = workspace_root / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        sub = workspace_root / "axm-commons"
        sub.mkdir()
        (sub / "pyproject.toml").touch()
        # No .venv in sub — must walk up to workspace_root

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["pytest", "--no-header"], sub)

            args = mock_run.call_args[0][0]
            # Must use uv run (not bare cmd)
            assert args[0] == "uv"
            assert "--directory" in args
            # --directory must point to the *subpackage*, not workspace root
            dir_idx = args.index("--directory")
            assert args[dir_idx + 1] == str(sub)

    def test_workspace_packages_member_uses_uv_run(self, tmp_path: Path) -> None:
        """Workspace member under packages/ uses uv run.

        Regression test for AXM-300: _find_venv stopped at the
        intermediate ``packages/`` directory (no ``pyproject.toml``),
        causing run_in_project to fall back to bare pytest.
        """
        from axm_audit.core.runner import run_in_project

        # workspace/
        # ├── .venv/bin/python
        # ├── pyproject.toml
        # └── packages/          ← no pyproject.toml
        #     └── axm-word/
        #         └── pyproject.toml
        workspace = tmp_path / "axm-office"
        workspace.mkdir()
        (workspace / "pyproject.toml").touch()
        venv_bin = workspace / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        packages = workspace / "packages"
        packages.mkdir()

        pkg = packages / "axm-word"
        pkg.mkdir()
        (pkg / "pyproject.toml").touch()

        with patch("axm_audit.core.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_in_project(["pytest", "--no-header"], pkg)

            args = mock_run.call_args[0][0]
            assert args[0] == "uv"
            assert "--directory" in args
            dir_idx = args.index("--directory")
            assert args[dir_idx + 1] == str(pkg)

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

    def test_typecheck_uses_project_mypy(self, tmp_path: Path) -> None:
        """TypeCheckRule does NOT inject mypy — uses the project venv's copy."""
        from axm_audit.core.rules.quality import TypeCheckRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.quality.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="", stderr="", returncode=0)
            TypeCheckRule().check(tmp_path)
            with_pkgs = mock.call_args[1].get("with_packages") or []
            assert "mypy" not in with_pkgs

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


# ── Tests for _build_test_report helper ──────────────────────────────


class TestBuildTestReport:
    """Tests for the extracted _build_test_report helper."""

    def test_build_test_report_helper(self, tmp_path: Path) -> None:
        """Tests that _build_test_report correctly constructs a TestReport."""
        from axm_audit.core.test_runner import _build_test_report

        report_data = {
            "summary": {
                "passed": 2,
                "failed": 1,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
            },
            "duration": 1.5,
            "tests": [
                {
                    "outcome": "failed",
                    "nodeid": "test_foo.py::test_bar",
                    "call": {
                        "crash": {
                            "message": "AssertionError: False is not True",
                            "path": "test_foo.py",
                            "lineno": 10,
                        },
                        "longrepr": "Traceback...\nAssertionError",
                    },
                }
            ],
        }

        per_file_cov = {"src/foo.py": 80.0}

        report = _build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file_cov,
            mode="failures",
            last_coverage=None,
        )

        assert report.passed == 2
        assert report.failed == 1
        assert report.coverage == 85.0
        assert len(report.failures) == 1
        assert report.failures[0].test == "test_foo.py::test_bar"
