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
