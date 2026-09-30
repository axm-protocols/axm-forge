"""A plugin-free target remains runnable without changing its environment."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.core.readiness import validation_readiness
from axm_audit.core.test_runner import run_tests

pytestmark = pytest.mark.e2e


def _inventory(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


@pytest.mark.parametrize("worktree", [False, True], ids=["project", "worktree"])
def test_plugin_free_package_matches_gate_without_sync(
    tmp_path: Path,
    worktree: bool,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "plugin-free"\nversion = "0.1.0"\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("VALUE = 1\n")
    (tmp_path / "tests").mkdir()
    test = tmp_path / "tests" / "test_sample.py"
    test.write_text("def test_sample():\n    assert 1 + 1 == 2\n")
    venv = tmp_path / ".venv"
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run([uv, "venv", str(venv)], check=True, capture_output=True)  # noqa: S603
    python = str(venv / "bin" / "python")
    subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", python, "pytest"],
        check=True,
        capture_output=True,
    )
    missing = subprocess.run(  # noqa: S603
        [
            python,
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('pytest_jsonreport') is None; "
            "assert importlib.util.find_spec('pytest_cov') is None",
        ],
        capture_output=True,
    )
    assert missing.returncode == 0, missing.stderr
    if worktree:
        source = tmp_path / "source"
        source.mkdir()
        gitdir = source / ".git" / "worktrees" / "candidate"
        gitdir.mkdir(parents=True)
        (gitdir / "commondir").write_text("../..")
        venv.rename(source / ".venv")
        venv = source / ".venv"
        (tmp_path / ".git").write_text(f"gitdir: {gitdir}")
    before = _inventory(venv)
    # Lint/type are separately covered; this regression measures the pytest boundary.
    with patch(
        "axm_audit.core.readiness.run_in_project",
        return_value=subprocess.CompletedProcess([], 0, "", ""),
    ):
        assert validation_readiness(tmp_path) == {}
        report = run_tests(tmp_path)
        assert report.passed == 1
        assert report.pytest_return_code == 0
        test.write_text("import a_module_that_does_not_exist\n")
        failure = validation_readiness(tmp_path)
    assert "a_module_that_does_not_exist" in failure["pytest"]
    assert _inventory(venv) == before
    assert not (tmp_path / "uv.lock").exists()
