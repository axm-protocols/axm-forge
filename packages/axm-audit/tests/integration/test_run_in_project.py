"""Split from ``test_subprocess_runner_layouts.py``."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


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
