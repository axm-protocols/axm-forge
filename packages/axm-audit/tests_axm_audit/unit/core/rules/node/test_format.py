"""Unit tests for the Node Prettier format rule."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.format import NodeFormatRule


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess standing in for a prettier invocation."""
    return subprocess.CompletedProcess(
        args=["prettier"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _make_node_project(tmp_path: Path) -> None:
    """Create the minimal package.json that marks a node project."""
    (tmp_path / "package.json").write_text('{"name":"n"}')


class TestNodeFormatMetadata:
    """The prettier rule shares the format contract with the python rule."""

    def test_rule_id(self) -> None:
        """Same rule_id as the Python format rule."""
        assert NodeFormatRule().rule_id == "QUALITY_FORMAT"

    def test_registered_under_node(self) -> None:
        """Registered under the node framework."""
        assert NodeFormatRule().framework is Framework.NODE


class TestNodeFormatScoring:
    """``check`` scores by the count of unformatted files."""

    def test_all_formatted_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No unformatted files yields 100."""
        _make_node_project(tmp_path)
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        monkeypatch.setattr(
            base_module,
            "run_node_tool",
            lambda *_a, **_k: _completed(stdout="All matched files use Prettier"),
        )
        result = NodeFormatRule().check(tmp_path)
        assert result.passed is True
        assert result.score == 100

    def test_unformatted_files_counted_from_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prettier reports on stderr; each [warn] file line deducts 5 points."""
        _make_node_project(tmp_path)
        stderr = (
            "[warn] src/a.ts\n"
            "[warn] src/b.ts\n"
            "[warn] src/c.ts\n"
            "[warn] Code style issues found in 3 files. Run Prettier to fix.\n"
        )
        monkeypatch.setattr(base_module, "node_tool_available", lambda _p, _b: True)
        # prettier --check exits 1 when files are unformatted.
        monkeypatch.setattr(
            base_module,
            "run_node_tool",
            lambda *_a, **_k: _completed(stderr=stderr, returncode=1),
        )
        result = NodeFormatRule().check(tmp_path)
        # 3 files (summary line excluded) -> 100 - 3*5 = 85, below the pass line.
        assert result.details["unformatted_count"] == 3
        assert result.score == 85
        assert result.passed is False
