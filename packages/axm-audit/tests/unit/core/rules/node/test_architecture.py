"""Unit tests for the Node architecture rules (madge + jscpd)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.architecture import (
    NodeCircularImportRule,
    NodeDuplicationRule,
)


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess for a node tool invocation."""
    return subprocess.CompletedProcess(
        args=["tool"], returncode=returncode, stdout=stdout, stderr=""
    )


def _node_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a node project with the tool available and a canned result."""
    (tmp_path / "package.json").write_text('{"name":"n"}')
    monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


class TestCircularImportRule:
    """``NodeCircularImportRule`` scores madge cycles."""

    def test_rule_id(self) -> None:
        """Shares the Python circular-import rule_id."""
        assert NodeCircularImportRule().rule_id == "ARCH_CIRCULAR"

    def test_no_cycles_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty cycle array scores 100."""
        _node_project(tmp_path, monkeypatch, _completed("[]"))
        assert NodeCircularImportRule().check(tmp_path).score == 100

    def test_cycles_deduct_twenty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each cycle deducts 20 points."""
        cycles = [["a.ts", "b.ts"], ["c.ts", "d.ts"]]
        _node_project(tmp_path, monkeypatch, _completed(json.dumps(cycles)))
        result = NodeCircularImportRule().check(tmp_path)
        assert result.details["cycle_count"] == 2
        assert result.score == 60


class TestDuplicationRule:
    """``NodeDuplicationRule`` scores jscpd duplication percentage."""

    def test_rule_id(self) -> None:
        """Shares the Python duplication rule_id."""
        assert NodeDuplicationRule().rule_id == "ARCH_DUPLICATION"

    def test_low_duplication_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplication under 3% passes."""
        payload = {"statistics": {"total": {"percentage": 1.0}}}
        _node_project(tmp_path, monkeypatch, _completed(json.dumps(payload)))
        result = NodeDuplicationRule().check(tmp_path)
        assert result.passed is True

    def test_high_duplication_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplication above the 3% pass threshold fails."""
        payload = {"statistics": {"total": {"percentage": 8.0}}}
        _node_project(tmp_path, monkeypatch, _completed(json.dumps(payload)))
        result = NodeDuplicationRule().check(tmp_path)
        assert result.passed is False
        assert result.details["duplication_pct"] == 8.0
