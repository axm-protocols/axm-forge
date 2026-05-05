"""Unit tests for :mod:`axm_mcp.verify_format`."""

from __future__ import annotations

from typing import Any

from axm_mcp.verify_format import format_verify_text


def _make(audit: Any = None, governance: Any = None) -> dict[str, Any]:
    return {"audit": audit, "governance": governance}


class TestHeader:
    def test_audit_skipped_when_none(self) -> None:
        text = format_verify_text(
            _make(
                governance={"score": 90, "grade": "A", "passed_count": 5, "failed": []}
            )
        )
        assert text.startswith("verify | audit: skipped")

    def test_governance_skipped_when_none(self) -> None:
        text = format_verify_text(
            _make(audit={"score": 80, "grade": "B", "passed": [], "failed": []})
        )
        assert "governance: skipped" in text.splitlines()[0]

    def test_audit_counts_passed_plus_failed(self) -> None:
        audit = {
            "score": 75,
            "grade": "C",
            "passed": ["a", "b", "c"],
            "failed": [{"rule_id": "X", "message": "oops"}],
        }
        text = format_verify_text(_make(audit=audit))
        assert "audit C 75 (3/4)" in text.splitlines()[0]

    def test_governance_uses_passed_count(self) -> None:
        gov = {
            "score": 90,
            "grade": "A",
            "passed_count": 7,
            "failed": [{"name": "chk", "message": "m"}],
        }
        text = format_verify_text(_make(governance=gov))
        assert "governance A 90 (7/8)" in text.splitlines()[0]


class TestFindingDetail:
    def _audit_with(self, failure: dict[str, Any]) -> dict[str, Any]:
        return _make(
            audit={"score": 0, "grade": "F", "passed": [], "failed": [failure]}
        )

    def test_text_field_used_directly(self) -> None:
        text = format_verify_text(
            self._audit_with({"rule_id": "R1", "message": "msg", "text": "• hi: a b c"})
        )
        assert "• hi: a b c" in text

    def test_details_str_truncated(self) -> None:
        long = "x" * 300
        text = format_verify_text(
            self._audit_with({"rule_id": "R", "message": "m", "details": long})
        )
        assert "…" in text

    def test_details_list_summary(self) -> None:
        text = format_verify_text(
            self._audit_with(
                {"rule_id": "R", "message": "m", "details": ["a", "b", "c", "d", "e"]}
            )
        )
        assert "a, b, c (+2 more)" in text

    def test_metadata_clusters_summary(self) -> None:
        clusters = [
            {"signal": "alpha", "members": ["t1", "t2"], "similarity": 0.9},
            {"signal": "alpha", "members": ["t3"], "similarity": 0.8},
            {"signal": "beta", "members": ["t4"], "similarity": 0.7},
        ]
        text = format_verify_text(
            self._audit_with(
                {"rule_id": "R", "message": "m", "metadata": {"clusters": clusters}}
            )
        )
        assert "signals:" in text
        assert "alpha=2" in text

    def test_no_detail_when_empty(self) -> None:
        text = format_verify_text(self._audit_with({"rule_id": "R", "message": "m"}))
        lines = text.splitlines()
        finding_lines = [line for line in lines if line.startswith("✗ R")]
        assert len(finding_lines) == 1
        idx = lines.index(finding_lines[0])
        rest = lines[idx + 1 :]
        assert all(
            not line.startswith("  ") or line.startswith("  fix:") for line in rest
        )

    def test_fix_hint_truncated_at_150(self) -> None:
        long_fix = "y" * 300
        text = format_verify_text(
            self._audit_with({"rule_id": "R", "message": "m", "fix_hint": long_fix})
        )
        for line in text.splitlines():
            if line.startswith("  fix:"):
                assert len(line) <= 157
                assert line.endswith("…")
                break
        else:
            raise AssertionError("no fix line found")

    def test_multiple_findings_preserve_order(self) -> None:
        failures = [
            {"rule_id": "FIRST", "message": "a"},
            {"rule_id": "SECOND", "message": "b"},
            {"rule_id": "THIRD", "message": "c"},
        ]
        text = format_verify_text(
            _make(audit={"score": 0, "grade": "F", "passed": [], "failed": failures})
        )
        i1 = text.index("FIRST")
        i2 = text.index("SECOND")
        i3 = text.index("THIRD")
        assert i1 < i2 < i3
