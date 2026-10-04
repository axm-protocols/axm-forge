"""Audit instruments honor transport runtimes without uv overlays."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm import DependencyEnvironment
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract

from axm_audit.core.runner import run_in_project

_REAL_POPEN = subprocess.Popen


def _no_uv(command: list[str], **kwargs: object) -> subprocess.Popen[str]:
    """Prevent any legacy bootstrap during the red demonstration."""
    assert command[0] != "uv", "contract runtime must never invoke uv"
    return _REAL_POPEN(command, **kwargs)  # type: ignore[arg-type]


def test_declared_runtime_beats_empty_local_venv(tmp_path: Path) -> None:
    """Runtime package requests do not replace the admitted interpreter."""
    local = tmp_path / ".venv/bin/python"
    local.parent.mkdir(parents=True)
    local.write_text("empty runtime")
    source = tmp_path / "src"
    source.mkdir()
    env = DependencyEnvironment(sys.executable, str(tmp_path), (str(source),))
    contract = WriteContract(str(tmp_path), dependency_environment=env)
    proc = MagicMock()
    proc.communicate.return_value = ("ok", "")
    proc.returncode = 0
    with (
        dependency_read_context(contract),
        patch("axm_audit.core.runner.subprocess.Popen", return_value=proc) as spawn,
    ):
        result = run_in_project(
            ["pytest", "--version"],
            tmp_path,
            with_packages=["pytest-json-report"],
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0
    assert spawn.call_args.args[0] == [sys.executable, "-m", "pytest", "--version"]
    assert spawn.call_args.kwargs["env"]["PYTHONPATH"] == str(source)


def test_declared_runtime_executes_candidate_module(tmp_path: Path) -> None:
    """A real child sees the candidate overlay in the declared interpreter."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "ruff.py").write_text("import sys; print(sys.executable)")
    env = DependencyEnvironment(sys.executable, str(tmp_path), (str(source),))
    with (
        dependency_read_context(
            WriteContract(str(tmp_path), dependency_environment=env)
        ),
        patch("axm_audit.core.runner.subprocess.Popen", side_effect=_no_uv),
    ):
        result = run_in_project(
            ["ruff", "--version"],
            tmp_path,
            with_packages=["uninstalled-package"],
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0
    assert result.stdout.strip() == sys.executable
    assert not (tmp_path / ".venv").exists()


def test_declared_runtime_missing_module_fails_without_install(tmp_path: Path) -> None:
    """An unavailable instrument fails explicitly rather than choosing another env."""
    env = DependencyEnvironment(sys.executable, str(tmp_path))
    with (
        dependency_read_context(
            WriteContract(str(tmp_path), dependency_environment=env)
        ),
        patch("axm_audit.core.runner.subprocess.Popen", side_effect=_no_uv),
    ):
        result = run_in_project(
            ["python", "-m", "axm_missing_instrument_for_test"],
            tmp_path,
            with_packages=["uninstalled-package"],
            capture_output=True,
            text=True,
        )
    assert result.returncode != 0
    assert "No module named" in result.stderr
    assert not (tmp_path / ".venv").exists()
