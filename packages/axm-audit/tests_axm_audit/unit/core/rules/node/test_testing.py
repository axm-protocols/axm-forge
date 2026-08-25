"""Unit tests for the Node Vitest testing rule."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.testing import NodeTestRule


def _vitest(
    payload: dict[str, int], returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    """Build a vitest JSON CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["vitest"], returncode=returncode, stdout=json.dumps(payload), stderr=""
    )


def _node_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a node project with vitest available and a canned result."""
    (tmp_path / "package.json").write_text('{"name":"n"}')
    monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


def test_all_passing_scores_100(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A full green suite scores 100."""
    payload = {"numTotalTests": 10, "numPassedTests": 10, "numFailedTests": 0}
    _node_project(tmp_path, monkeypatch, _vitest(payload))
    result = NodeTestRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100


def test_empty_suite_is_hard_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero tests is a hard fail (passWithNoTests false-green guard)."""
    payload = {"numTotalTests": 0, "numPassedTests": 0, "numFailedTests": 0}
    _node_project(tmp_path, monkeypatch, _vitest(payload))
    result = NodeTestRule().check(tmp_path)
    assert result.passed is False
    assert result.score == 0
    assert "No tests" in result.message


def test_failures_lower_score_and_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed tests drop the score and fail the rule (rc=1 is a finding)."""
    payload = {"numTotalTests": 10, "numPassedTests": 8, "numFailedTests": 2}
    _node_project(tmp_path, monkeypatch, _vitest(payload, returncode=1))
    result = NodeTestRule().check(tmp_path)
    assert result.score == 80
    assert result.passed is False
