"""Unit tests for the Node ESLint lint rule."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.lint import NodeLintRule


def _completed(stdout: str, returncode: int = 1) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess standing in for an eslint invocation."""
    return subprocess.CompletedProcess(
        args=["eslint"], returncode=returncode, stdout=stdout, stderr=""
    )


class TestNodeLintRuleMetadata:
    """The node lint rule shares the lint contract with the python rule."""

    def test_rule_id_matches_python_lint(self) -> None:
        """Same rule_id so the lint category is framework-agnostic."""
        assert NodeLintRule().rule_id == "QUALITY_LINT"

    def test_registered_under_node_framework(self) -> None:
        """The decorator places the rule under the node framework."""
        assert NodeLintRule().framework is Framework.NODE


class TestNodeLintRuleCheck:
    """``check`` over the relevant project states."""

    def test_no_package_json_skips_green(self, tmp_path: Path) -> None:
        """A directory without package.json is not a node project — pass, INFO."""
        result = NodeLintRule().check(tmp_path)
        assert result.passed is True
        assert "skipped" in result.message.lower()

    def test_eslint_unavailable_fails_loud(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """package.json present but eslint not installed must fail, never green."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: False)
        result = NodeLintRule().check(tmp_path)
        assert result.passed is False

    def test_clean_eslint_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero eslint findings yields a passing 100 score."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        clean = '[{"errorCount":0,"warningCount":0}]'
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(clean, 0)
        )
        result = NodeLintRule().check(tmp_path)
        assert result.passed is True
        assert result.score == 100

    def test_issues_deduct_two_each(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Three findings deduct 2 points each (100 - 3*2 = 94), like the py rule."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        report = '[{"errorCount":2,"warningCount":1}]'
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(report, 1)
        )
        result = NodeLintRule().check(tmp_path)
        assert result.score == 94
        assert result.passed is False

    def test_env_failure_is_not_green(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A timeout (rc=124) is an env failure — fail loud with a zero score."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed("", 124)
        )
        result = NodeLintRule().check(tmp_path)
        assert result.passed is False
        assert result.score == 0
