"""Declared Python instrument subprocess checks."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from axm import DependencyEnvironment
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract

from axm_audit.core.runner import run_in_project
from tests_axm_audit.e2e._instrument_helpers import _no_uv

pytestmark = pytest.mark.e2e


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
