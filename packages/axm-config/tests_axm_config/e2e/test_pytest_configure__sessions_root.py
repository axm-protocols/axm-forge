"""Subprocesses spawned inside a sandboxed pytest session inherit the sandbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = ["pytester"]

_OVERRIDES = (
    "AXM_PATHS_SESSIONS_ROOT",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_WARDEN_SOCKET",
    "AXM_TICKETS_DB_PATH",
    "AXM_WARDEN_LOG_PATH",
    "AXM_HOME",
    "AXM_PROFILE",
)

_INNER_CHILD = """
import json
import subprocess
import sys
from pathlib import Path

from axm_config.sandbox import active_sandbox


def test_child():
    sandbox = active_sandbox()
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "from axm_config.paths import sessions_root; print(sessions_root())",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = {
        "root": None if sandbox is None else str(sandbox.root),
        "child": child.stdout.strip(),
    }
    Path(__file__).with_name("report.json").write_text(json.dumps(report))
"""


def _under(path: Path, base: Path) -> bool:
    return path.resolve().is_relative_to(base.resolve())


@pytest.mark.e2e
def test_subprocess_in_dev_session_inherits_sandbox(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC7: a python -c child of a dev-profile session resolves in the sandbox."""
    for name in _OVERRIDES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AXM_PROFILE", "dev")
    home = Path(os.environ["HOME"])
    pytester.makepyfile(test_inner_child=_INNER_CHILD)

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
    report: dict[str, Any] = json.loads((pytester.path / "report.json").read_text())
    assert report["root"] is not None
    child = Path(report["child"])
    assert child.is_relative_to(Path(report["root"]))
    assert not _under(child, home / "axm")
    assert not _under(child, home / ".axm")
