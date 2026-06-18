"""Split from ``test_subprocess_runner_layouts.py``."""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


def _fake_popen(returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.pid = 4242
    proc.returncode = returncode
    proc.communicate.return_value = ("", "")
    return proc


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

        with patch("axm_audit.core.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _fake_popen()
            run_in_project(["ruff", "check", "src"], tmp_path)

            args = mock_popen.call_args[0][0]
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

        with patch("axm_audit.core.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _fake_popen()
            run_in_project(["pytest", "--no-header"], pkg)

            args = mock_popen.call_args[0][0]
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

        with patch("axm_audit.core.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _fake_popen()
            run_in_project(
                ["pytest", "--json-report"],
                tmp_path,
                with_packages=["pytest-json-report", "pytest-cov"],
            )

            args = mock_popen.call_args[0][0]
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

        with patch("axm_audit.core.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _fake_popen()
            run_in_project(["ruff", "check"], tmp_path, with_packages=None)

            args = mock_popen.call_args[0][0]
            assert args == ["uv", "run", "--directory", str(tmp_path), "ruff", "check"]


def _pid_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` is still alive (POSIX)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user -> alive.
        return True
    return True


@pytest.mark.skipif(
    not hasattr(os, "setsid"), reason="POSIX process-group semantics required"
)
def test_forked_child_killed_on_timeout(tmp_path: Path) -> None:
    """AC1, AC4: a long-lived forked grandchild is killed when the parent times out.

    The parent spawns a detached child that writes its PID to a file and sleeps
    60s, then the parent itself sleeps long enough to trip the timeout. After
    ``run_in_project`` returns rc=124, the forked child must no longer be alive:
    killing only the direct process would leave the child orphaned and running.
    """
    from axm_audit.core.runner import run_in_project

    pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, time; "
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid())); "
        "time.sleep(60)"
    )
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        "time.sleep(60)"
    )

    result = run_in_project(
        [sys.executable, "-c", parent_code],
        tmp_path,
        timeout=3,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 124

    # Wait for the grandchild to record its PID.
    deadline = time.time() + 5
    while not pid_file.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert pid_file.exists(), "forked child never recorded its PID"
    child_pid = int(pid_file.read_text().strip())

    # Give the kill signal time to propagate to the whole process group.
    deadline = time.time() + 5
    while _pid_alive(child_pid) and time.time() < deadline:
        time.sleep(0.1)

    leaked = _pid_alive(child_pid)
    if leaked:
        # Best-effort cleanup so a failing assertion does not leak a process.
        with contextlib.suppress(ProcessLookupError):
            os.kill(child_pid, 9)
    assert not leaked, (
        f"forked child {child_pid} survived the timeout (process subtree leaked)"
    )


# --- AC3 real-subprocess contract (no mock; light subprocess, no venv) ---


def test_timeout_returns_124_synthetic(tmp_path: Path) -> None:
    """AC3: real timeout yields synthetic CompletedProcess rc=124 + message.

    No venv in tmp_path -> command runs directly with cwd (no uv).
    """
    from axm_audit.core.runner import run_in_project

    result = run_in_project(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        tmp_path,
        timeout=1,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 124
    assert "timed out" in result.stderr.lower()


def test_success_returns_completed_process(tmp_path: Path) -> None:
    """AC3: a fast successful command returns a CompletedProcess rc=0."""
    from axm_audit.core.runner import run_in_project

    result = run_in_project(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        tmp_path,
        timeout=10,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
