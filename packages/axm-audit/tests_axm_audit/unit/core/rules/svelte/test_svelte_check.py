"""Unit tests for the Svelte svelte-check rule (the svelte delta)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.svelte.svelte_check import SvelteCheckRule


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess for a svelte-check invocation."""
    return subprocess.CompletedProcess(
        args=["svelte-check"], returncode=returncode, stdout=stdout, stderr=""
    )


def _svelte_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a svelte project with svelte-check available and a canned result."""
    (tmp_path / "package.json").write_text('{"devDependencies":{"svelte":"^5"}}')
    monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


def test_registered_under_svelte() -> None:
    """The svelte-check rule belongs to the svelte framework delta."""
    assert SvelteCheckRule().framework is Framework.SVELTE


def test_clean_scores_100(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No svelte-check errors scores 100."""
    _svelte_project(tmp_path, monkeypatch, _completed(""))
    assert SvelteCheckRule().check(tmp_path).score == 100


def test_errors_deduct_five_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each ERROR row deducts 5; rc=1 is a finding, not an env-failure."""
    machine = (
        '1700000000000 ERROR "src/App.svelte" 1:1 "Type error"\n'
        '1700000000001 ERROR "src/App.svelte" 2:1 "Another"\n'
        '1700000000002 WARNING "src/App.svelte" 3:1 "a11y warning"\n'
    )
    _svelte_project(tmp_path, monkeypatch, _completed(machine, returncode=1))
    result = SvelteCheckRule().check(tmp_path)
    # 2 ERROR rows (the WARNING is ignored) -> 100 - 2*5 = 90.
    assert result.details["error_count"] == 2
    assert result.score == 90
