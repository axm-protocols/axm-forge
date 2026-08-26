"""Unit tests for the Node tsc type-check rule."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.typecheck import NodeTypeCheckRule


def _completed(stdout: str, returncode: int) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess standing in for a tsc invocation."""
    return subprocess.CompletedProcess(
        args=["tsc"], returncode=returncode, stdout=stdout, stderr=""
    )


def _make_node_project(tmp_path: Path) -> None:
    """Create the minimal package.json that marks a node project."""
    (tmp_path / "package.json").write_text('{"name":"n"}')


class TestNodeTypeCheckMetadata:
    """The tsc rule shares the type contract with the python rule."""

    def test_rule_id(self) -> None:
        """Same rule_id as the Python type rule."""
        assert NodeTypeCheckRule().rule_id == "QUALITY_TYPE"

    def test_registered_under_node(self) -> None:
        """Registered under the node framework."""
        assert NodeTypeCheckRule().framework is Framework.NODE


class TestNodeTypeCheckScoring:
    """``check`` scores by the tsc error count."""

    def test_clean_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No tsc errors yields 100, passing."""
        _make_node_project(tmp_path)
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed("", 0)
        )
        result = NodeTypeCheckRule().check(tmp_path)
        assert result.passed is True
        assert result.score == 100

    def test_errors_deduct_five_each(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two tsc errors deduct 5 each (100 - 2*5 = 90)."""
        _make_node_project(tmp_path)
        out = (
            "src/a.ts(1,7): error TS2322: Type 'string' is not assignable.\n"
            "src/b.ts(3,1): error TS2304: Cannot find name 'x'.\n"
            "Found 2 errors.\n"
        )
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        # tsc exits 2 when it FOUND errors — must be scored, not env-failure.
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(out, 2)
        )
        result = NodeTypeCheckRule().check(tmp_path)
        assert result.score == 90
        assert result.details["error_count"] == 2

    def test_exit_two_with_errors_is_not_env_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rc=2 from tsc is a finding, not a blocked/zero env-failure result."""
        _make_node_project(tmp_path)
        out = "src/a.ts(1,7): error TS2322: bad.\n"
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(out, 2)
        )
        result = NodeTypeCheckRule().check(tmp_path)
        # Would be score 0 / "BLOCKED" if rc=2 were treated as env-failure.
        assert result.score == 95
        assert "BLOCKED" not in result.message

    def test_svelte_module_diagnostics_are_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Named-export errors on ``*.svelte`` are svelte-check's job, not tsc's.

        The ``declare module '*.svelte'`` shipped by svelte only exports the
        default component, so importing a ``<script module>`` named export trips
        TS2614 under bare tsc — a false positive covered by SVELTE_CHECK.
        """
        _make_node_project(tmp_path)
        out = (
            "src/a.test.ts(7,10): error TS2614: Module '\"*.svelte\"' has no "
            "exported member 'bandColor'.\n"
            "src/b.test.ts(8,3): error TS2614: Module '\"*.svelte\"' has no "
            "exported member 'bucketLoad'.\n"
            "Found 2 errors.\n"
        )
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(out, 2)
        )
        result = NodeTypeCheckRule().check(tmp_path)
        assert result.score == 100
        assert result.details["error_count"] == 0

    def test_real_errors_counted_alongside_ignored_svelte_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A genuine TS error still counts even when svelte noise is present."""
        _make_node_project(tmp_path)
        out = (
            "src/a.test.ts(7,10): error TS2614: Module '\"*.svelte\"' has no "
            "exported member 'bandColor'.\n"
            "src/b.ts(3,1): error TS7006: Parameter 'l' implicitly has 'any'.\n"
            "Found 2 errors.\n"
        )
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module, "run_node_tool", lambda *_a, **_k: _completed(out, 2)
        )
        result = NodeTypeCheckRule().check(tmp_path)
        # Only the real TS7006 counts: 100 - 1*5 = 95.
        assert result.score == 95
        assert result.details["error_count"] == 1
