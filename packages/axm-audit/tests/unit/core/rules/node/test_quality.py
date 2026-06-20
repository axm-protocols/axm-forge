"""Unit tests for the node diff-size and eslint-security rules."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.quality import NodeDiffSizeRule, NodeSecurityLintRule


def test_diff_size_reuses_python_logic() -> None:
    """NodeDiffSizeRule is the Python rule registered for node."""
    assert NodeDiffSizeRule().rule_id == "QUALITY_DIFF_SIZE"
    assert NodeDiffSizeRule().framework is Framework.NODE


def test_diff_size_skips_outside_git(tmp_path: Path) -> None:
    """Outside a git repo the diff-size rule skips (inherited behaviour)."""
    result = NodeDiffSizeRule().check(tmp_path)
    assert result.passed is True


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


class TestSecurityLint:
    """``NodeSecurityLintRule`` counts eslint-plugin-security findings."""

    def test_rule_id(self) -> None:
        """Shares the Python security rule_id."""
        assert NodeSecurityLintRule().rule_id == "QUALITY_SECURITY"

    def test_only_security_rules_counted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only ``security/*`` ruleIds count; other lint messages are ignored."""
        messages = [
            {"ruleId": "security/detect-eval-with-expression"},
            {"ruleId": "security/detect-non-literal-fs-filename"},
            {"ruleId": "no-unused-vars"},
        ]
        _node_project(tmp_path, monkeypatch, _eslint(messages))
        result = NodeSecurityLintRule().check(tmp_path)
        assert result.details["finding_count"] == 2
        assert result.score == 70
        assert result.passed is False

    def test_clean_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No security findings scores 100."""
        _node_project(tmp_path, monkeypatch, _eslint([{"ruleId": "no-unused-vars"}]))
        assert NodeSecurityLintRule().check(tmp_path).passed is True
