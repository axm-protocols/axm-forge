"""Unit tests for the knip-backed dependency and dead-code rules."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.knip import NodeDeadCodeRule, NodeDependencyRule


def _knip(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """Build a knip JSON CompletedProcess (rc=0 thanks to --no-exit-code)."""
    return subprocess.CompletedProcess(
        args=["knip"], returncode=0, stdout=json.dumps(payload), stderr=""
    )


def _node_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a node project with knip available and a canned result."""
    (tmp_path / "package.json").write_text('{"name":"n"}')
    monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


class TestDependencyRule:
    """``NodeDependencyRule`` scores unused/unlisted deps."""

    def test_rule_id(self) -> None:
        """Lives under the deps category with the hygiene rule_id."""
        assert NodeDependencyRule().rule_id == "DEPS_HYGIENE"

    def test_clean_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No dependency issues scores 100."""
        _node_project(tmp_path, monkeypatch, _knip({"files": [], "issues": []}))
        assert NodeDependencyRule().check(tmp_path).score == 100

    def test_unused_and_unlisted_counted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unused deps + unlisted deps each deduct 10."""
        payload = {
            "files": [],
            "issues": [
                {"dependencies": ["lodash"], "unlisted": ["axios"]},
            ],
        }
        _node_project(tmp_path, monkeypatch, _knip(payload))
        result = NodeDependencyRule().check(tmp_path)
        assert result.details["issue_count"] == 2
        assert result.score == 80


class TestDeadCodeRule:
    """``NodeDeadCodeRule`` scores unused files + exports."""

    def test_rule_id(self) -> None:
        """Shares the Python dead-code rule_id."""
        assert NodeDeadCodeRule().rule_id == "QUALITY_DEAD_CODE"

    def test_unused_files_and_exports_counted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Top-level unused files plus per-file unused exports both count."""
        payload = {
            "files": ["src/orphan.ts"],
            "issues": [{"exports": ["unusedFn"], "types": ["UnusedT"]}],
        }
        _node_project(tmp_path, monkeypatch, _knip(payload))
        result = NodeDeadCodeRule().check(tmp_path)
        # 1 file + 1 export + 1 type = 3 -> 100 - 30 = 70.
        assert result.details["unused_count"] == 3
        assert result.score == 70
