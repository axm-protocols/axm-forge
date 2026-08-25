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

    def _wire_jscpd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, percentage: float
    ) -> None:
        """Wire jscpd available + a run that writes a report file to --output.

        jscpd emits nothing structured on stdout; it writes
        ``jscpd-report.json`` to the ``--output`` directory. The rule reads that
        file, so the mock must reproduce that side effect (a stdout-only mock
        would silently exercise the old false-green path).
        """
        (tmp_path / "package.json").write_text('{"name":"n"}')
        module = "axm_audit.core.rules.node.architecture"
        monkeypatch.setattr(f"{module}.node_tool_available", lambda _p, _b: True)

        def _fake_run(
            _binary: str, args: list[str], _project: Path, **_kw: object
        ) -> subprocess.CompletedProcess[str]:
            out_dir = Path(args[args.index("--output") + 1])
            report = {"statistics": {"total": {"percentage": percentage}}}
            (out_dir / "jscpd-report.json").write_text(json.dumps(report))
            return _completed("")

        monkeypatch.setattr(f"{module}.run_node_tool", _fake_run)

    def test_low_duplication_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplication under 3% passes."""
        self._wire_jscpd(tmp_path, monkeypatch, 1.0)
        result = NodeDuplicationRule().check(tmp_path)
        assert result.passed is True

    def test_high_duplication_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplication above the 3% pass threshold fails."""
        self._wire_jscpd(tmp_path, monkeypatch, 8.0)
        result = NodeDuplicationRule().check(tmp_path)
        assert result.passed is False
        assert result.details["duplication_pct"] == 8.0

    def test_report_file_read_not_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: the pct comes from the report file, never stdout.

        The old rule JSON-decoded stdout (always ``[]`` for jscpd) → a permanent
        false-green. Here stdout is jscpd's human summary while the *file* says
        48.75% — the rule must fail, proving it reads the file.
        """
        self._wire_jscpd(tmp_path, monkeypatch, 48.75)
        result = NodeDuplicationRule().check(tmp_path)
        assert result.passed is False
        assert result.score == 0
