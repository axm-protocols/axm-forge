"""Tests for run_in_project helper and rule subprocess integration."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Tests for find_venv helper ───────────────────────────────────────


def _layout_local(tmp_path: Path) -> tuple[Path, Path]:
    """.venv directly in project_path."""
    (tmp_path / "pyproject.toml").touch()
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()
    return tmp_path, tmp_path / ".venv"


def _layout_workspace_root(tmp_path: Path) -> tuple[Path, Path]:
    """.venv at workspace root, subpackage as direct child (uv workspace siblings)."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "pyproject.toml").touch()
    venv_bin = workspace_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    subpackage = workspace_root / "my-lib"
    subpackage.mkdir()
    (subpackage / "pyproject.toml").touch()
    return subpackage, workspace_root / ".venv"


def _layout_packages_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Workspace with intermediate packages/ dir lacking pyproject.toml."""
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
    packages.mkdir()  # no pyproject.toml

    pkg = packages / "my-pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").touch()
    return pkg, workspace / ".venv"


def _layout_flat_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Flat workspace layout: subpackage as direct sibling under workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").touch()
    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    pkg = workspace / "my-lib"
    pkg.mkdir()
    (pkg / "pyproject.toml").touch()
    return pkg, workspace / ".venv"


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(_layout_local, id="local_venv"),
        pytest.param(_layout_workspace_root, id="workspace_root_venv"),
        pytest.param(_layout_packages_dir, id="packages_layout"),
        pytest.param(_layout_flat_workspace, id="flat_workspace"),
    ],
)
def test_find_venv_locates_venv(
    build: Callable[[Path], tuple[Path, Path]],
    tmp_path: Path,
) -> None:
    """find_venv walks up to the first .venv across supported workspace layouts."""
    from axm_audit.core.runner import find_venv

    target, expected = build(tmp_path)
    assert find_venv(target) == expected


class TestFindVenv:
    """Tests for find_venv edge cases (None results, depth bound)."""

    def test_returns_none_when_no_venv(self, tmp_path: Path) -> None:
        """Returns None when no .venv exists anywhere in the project tree."""
        from axm_audit.core.runner import find_venv

        (tmp_path / "pyproject.toml").touch()
        result = find_venv(tmp_path)
        assert result is None

    def test_find_venv_bounded_depth(self, tmp_path: Path) -> None:
        """Returns None when .venv is beyond _MAX_VENV_SEARCH_DEPTH levels up."""
        from axm_audit.core.runner import _MAX_VENV_SEARCH_DEPTH, find_venv

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

        result = find_venv(deep)
        assert result is None


# ── Tests for run_in_project helper ──────────────────────────────────


class TestRunInProjectIntegration:
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

    @pytest.mark.parametrize(
        ("build_layout",),
        [
            pytest.param(
                "direct_sibling",
                id="workspace_subpackage_direct_sibling",
            ),
            pytest.param(
                "packages_dir",
                id="workspace_subpackage_packages_dir",
            ),
        ],
    )
    def test_workspace_subpackage_uses_uv_run(
        self, tmp_path: Path, build_layout: str
    ) -> None:
        """Workspace member uses uv run when .venv is at monorepo root.

        Covers both direct-sibling (AXM-290) and packages/-intermediary
        (AXM-300) layouts.
        """
        from axm_audit.core.runner import run_in_project

        if build_layout == "direct_sibling":
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
            pkg = sub
        else:
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


class TestRulesUseRunInProjectIntegration:
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

    def test_bandit_uses_run_in_project(self, tmp_path: Path) -> None:
        """SecurityRule should call run_in_project."""
        from axm_audit.core.rules.security import SecurityRule

        (tmp_path / "src").mkdir()

        with patch("axm_audit.core.rules.security.run_in_project") as mock:
            mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            SecurityRule().check(tmp_path)
            mock.assert_called_once()
            assert mock.call_args[0][0][0] == "bandit"


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


class TestWithPackagesInjectionIntegration:
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


class TestBuildTestReport:
    """Tests for the extracted _build_test_report helper."""

    def test_build_test_report_helper(self, tmp_path: Path) -> None:
        """Tests that _build_test_report correctly constructs a TestReport."""
        from axm_audit.core.test_runner import build_test_report

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

        report = build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file_cov,
            mode="failures",
            last_coverage=None,
        )

        assert report.passed == 2
        assert report.failed == 1
        assert report.coverage == 85.0
        assert report.failures is not None
        assert len(report.failures) == 1
        assert report.failures[0].test == "test_foo.py::test_bar"
