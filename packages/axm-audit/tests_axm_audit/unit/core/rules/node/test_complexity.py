"""Unit tests for the Node ESLint complexity rule."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.complexity import NodeComplexityRule


def _eslint(messages: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
    """Build an eslint JSON CompletedProcess with one file's messages."""
    report = [{"filePath": "src/a.ts", "messages": messages}]
    return subprocess.CompletedProcess(
        args=["eslint"], returncode=1, stdout=json.dumps(report), stderr=""
    )


def _node_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a node project with eslint available and a canned result."""
    (tmp_path / "package.json").write_text('{"name":"n"}')
    monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


def test_rule_id_matches_python() -> None:
    """Same rule_id as the Python complexity rule."""
    assert NodeComplexityRule().rule_id == "QUALITY_COMPLEXITY"


def test_no_complexity_findings_scores_100(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An eslint run with no complexity messages scores 100."""
    _node_project(tmp_path, monkeypatch, _eslint([]))
    result = NodeComplexityRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100


def test_counts_only_complexity_rule_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only `complexity` and `sonarjs/cognitive-complexity` messages count."""
    messages = [
        {"ruleId": "complexity", "message": "cc 12"},
        {"ruleId": "sonarjs/cognitive-complexity", "message": "cog 18"},
        {"ruleId": "no-unused-vars", "message": "unrelated"},
    ]
    _node_project(tmp_path, monkeypatch, _eslint(messages))
    result = NodeComplexityRule().check(tmp_path)
    # 2 complexity violations * 10 -> 80; the lint message is ignored.
    assert result.details["violation_count"] == 2
    assert result.score == 80
