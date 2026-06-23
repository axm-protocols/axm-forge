"""End-to-end tests for the ``axm-config`` CLI (subprocess black box).

Each test invokes the installed console script through ``uv run`` against an
isolated ``HOME`` so the real ``~/.axm`` store is never touched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PKG_DIR = Path(__file__).resolve().parents[2]


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess[str]:
    """Run ``axm-config <args>`` with an isolated HOME, capturing text output."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        ["uv", "run", "axm-config", *args],
        cwd=PKG_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.e2e
def test_set_then_get_roundtrip(tmp_path: Path) -> None:
    """AC1: a value set via the CLI is read back by a subsequent get."""
    set_result = _run(["set", "demo", "greeting", "hello"], tmp_path)
    assert set_result.returncode == 0, set_result.stderr

    get_result = _run(["get", "demo", "greeting"], tmp_path)
    assert get_result.returncode == 0, get_result.stderr
    assert "hello" in get_result.stdout


@pytest.mark.e2e
def test_path_prints_home(tmp_path: Path) -> None:
    """AC2: ``path`` prints the resolved ~/.axm home directory."""
    result = _run(["path"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("/.axm")


@pytest.mark.e2e
def test_doctor_prints_provenance(tmp_path: Path) -> None:
    """AC2: ``doctor <ns>`` reports per-key provenance and exits 0."""
    set_result = _run(["set", "demo", "greeting", "hi"], tmp_path)
    assert set_result.returncode == 0, set_result.stderr

    result = _run(["doctor", "demo"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "file" in result.stdout
