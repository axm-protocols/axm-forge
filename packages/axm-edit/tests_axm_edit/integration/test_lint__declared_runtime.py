"""All edit lint steps share the declared runtime."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from axm import DependencyEnvironment
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract

from axm_edit.services import lint
from axm_edit.tools.batch_edit import _run_ruff


def test_all_lint_steps_use_declared_python(tmp_path: Path) -> None:
    """Probe, checks, fix and format cannot invoke uv or choose a native venv."""
    (tmp_path / "src").mkdir()
    local = tmp_path / ".venv/bin/python"
    local.parent.mkdir(parents=True)
    local.write_text("empty runtime")
    target = tmp_path / "src/sample.py"
    target.write_text("value = 1")
    env = DependencyEnvironment(sys.executable, str(tmp_path), (str(tmp_path / "src"),))
    contract = WriteContract(str(tmp_path), dependency_environment=env)
    lint._RUFF_AVAILABLE_CACHE.clear()
    completed = subprocess.CompletedProcess([], 0, "", "")
    with (
        dependency_read_context(contract),
        patch("axm_edit.tools.batch_edit.ruff_available", lint.ruff_available),
        patch("subprocess.run", return_value=completed) as run,
    ):
        assert _run_ruff(tmp_path, [target]) == ([], [])
    assert run.call_count == 5
    for call in run.call_args_list:
        assert call.args[0][:3] == [sys.executable, "-m", "ruff"]
        assert call.kwargs["env"]["PYTHONPATH"] == str(tmp_path / "src")


def test_lint_probe_contract_does_not_reuse_legacy_cache(tmp_path: Path) -> None:
    """A legacy negative probe cannot suppress the declared runtime."""
    lint._RUFF_AVAILABLE_CACHE[tmp_path.resolve()] = False
    env = DependencyEnvironment(sys.executable, str(tmp_path))
    with (
        dependency_read_context(
            WriteContract(str(tmp_path), dependency_environment=env)
        ),
        patch(
            "subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")
        ),
    ):
        assert lint.ruff_available(tmp_path)


def test_lint_missing_declared_tool_reports_runtime(tmp_path: Path) -> None:
    """Optional lint skips retain the bounded runtime probe failure."""
    env = DependencyEnvironment(sys.executable, str(tmp_path))
    completed = subprocess.CompletedProcess([], 1, "", "No module named ruff")
    warnings: list[str] = []
    with (
        dependency_read_context(
            WriteContract(str(tmp_path), dependency_environment=env)
        ),
        patch("axm_edit.tools.batch_edit.ruff_available", lint.ruff_available),
        patch("subprocess.run", return_value=completed),
    ):
        assert _run_ruff(tmp_path, [], warnings=warnings) == ([], [])
    assert len(warnings) == 1
    assert sys.executable in warnings[0]
    assert "No module named ruff" in warnings[0]
    assert "lint skipped" in warnings[0]
