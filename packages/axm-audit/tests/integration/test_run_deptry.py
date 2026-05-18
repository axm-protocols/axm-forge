"""Split from ``test_deptry_first_party.py``."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.dependencies import run_deptry


def test_deptry_namespace_no_false_positives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_deptry passes --known-first-party for namespace pkgs."""
    # Avoids DEP003 false positives for namespace packages.
    # Set up a namespace package structure
    (tmp_path / "src" / "openleaf" / "performance").mkdir(parents=True)
    (tmp_path / "src" / "openleaf" / "performance" / "__init__.py").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

    captured_cmds: list[list[str]] = []

    def fake_run_in_project(
        cmd: list[str],
        project_path: Path,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured_cmds.append(cmd)
        # Write empty JSON array to the tmp file (path is last arg of --json-output)
        json_idx = cmd.index("--json-output")
        json_path = Path(cmd[json_idx + 1])
        json_path.write_text("[]")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "axm_audit.core.rules.dependencies.run_in_project", fake_run_in_project
    )

    result = run_deptry(tmp_path)

    assert result == []
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "--known-first-party" in cmd
    kfp_idx = cmd.index("--known-first-party")
    assert cmd[kfp_idx + 1] == "openleaf"
