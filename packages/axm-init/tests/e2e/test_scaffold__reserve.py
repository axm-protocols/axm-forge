"""E2E: the ``--json`` CLI path must exit non-zero on failure.

Regression guard for the false-green where ``scaffold``/``reserve`` in
``--json`` mode printed the payload and returned exit 0 even on failure —
poisoning any CI/script that routes on ``$?``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_scaffold_json_failure_exits_nonzero_and_carries_message(
    tmp_path: Path,
) -> None:
    """``scaffold --member`` outside a workspace fails: exit != 0, JSON error."""
    proc = subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "scaffold",
            str(tmp_path),
            "--member",
            "my-lib",
            "--org",
            "Org",
            "--author",
            "Author",
            "--email",
            "a@b.com",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0, proc.stdout
    payload = json.loads(proc.stdout)
    assert "workspace" in json.dumps(payload).lower()


def test_scaffold_mutual_exclusion_json_exits_nonzero(tmp_path: Path) -> None:
    """``--workspace`` + ``--member`` together: exit != 0 even in JSON mode."""
    proc = subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "scaffold",
            str(tmp_path),
            "--workspace",
            "--member",
            "my-lib",
            "--org",
            "Org",
            "--author",
            "Author",
            "--email",
            "a@b.com",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "error" in json.loads(proc.stdout)


def test_reserve_json_missing_identity_exits_nonzero(tmp_path: Path) -> None:
    """``reserve --json`` with unresolvable identity: exit != 0, JSON error.

    Runs in an isolated HOME/cwd with no git config so author/email cannot be
    resolved, driving the failure branch deterministically without touching
    PyPI.
    """
    env = {
        "HOME": str(tmp_path),
        "PATH": _system_path(),
        "GIT_CONFIG_GLOBAL": str(tmp_path / "nonexistent-gitconfig"),
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    proc = subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "reserve",
            "some-name",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
        env=env,
    )

    assert proc.returncode != 0, proc.stdout
    assert "error" in json.loads(proc.stdout)


def _system_path() -> str:
    """Return a PATH that still resolves ``uv`` and ``git``."""
    import os

    return os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")
