"""Unit tests for :mod:`axm_mcp.verify_format`."""

from __future__ import annotations

from typing import Any

from axm_mcp.verify_format import format_verify_text


def _make(audit: Any = None, governance: Any = None) -> dict[str, Any]:
    return {"audit": audit, "governance": governance}


def _audit_with(failure: dict[str, Any]) -> dict[str, Any]:
    return _make(audit={"score": 0, "grade": "F", "passed": [], "failed": [failure]})


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


class TestTextField:
    def test_text_field_used_directly(self) -> None:
        text = format_verify_text(
            _audit_with({"rule_id": "R1", "message": "msg", "text": "• hi: a b c"})
        )
        assert "  • hi: a b c" in text

    def test_text_multiline_is_indented_uniformly(self) -> None:
        body = "• line one\n• line two\n• line three"
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "text": body})
        )
        lines = text.splitlines()
        bullets = [line for line in lines if "line" in line]
        assert bullets == ["  • line one", "  • line two", "  • line three"]

    def test_text_priority_over_details(self) -> None:
        text = format_verify_text(
            _audit_with(
                {
                    "rule_id": "R",
                    "message": "m",
                    "text": "from text",
                    "details": ["from details"],
                }
            )
        )
        assert "from text" in text
        assert "from details" not in text


class TestDetailsStr:
    def test_details_str_not_truncated(self) -> None:
        long = "x" * 300
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": long})
        )
        assert "…" not in text
        assert long in text

    def test_details_str_indented(self) -> None:
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": "single line"})
        )
        assert "  single line" in text

    def test_details_str_multiline_indented(self) -> None:
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": "a\nb"})
        )
        lines = text.splitlines()
        assert "  a" in lines
        assert "  b" in lines


class TestDetailsList:
    def test_short_list_renders_each_item(self) -> None:
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": ["a", "b", "c"]})
        )
        for expected in ("  - a", "  - b", "  - c"):
            assert expected in text
        assert "more)" not in text

    def test_long_list_caps_at_30_with_more(self) -> None:
        items = [f"item-{i}" for i in range(45)]
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": items})
        )
        assert "  - item-0" in text
        assert "  - item-29" in text
        assert "  - item-30" not in text
        assert "  (+15 more)" in text

    def test_dict_items_rendered_compact(self) -> None:
        items = [{"file": "a.py", "line": 12, "msg": "boom"}]
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "details": items})
        )
        assert "  - a.py:12 boom" in text


class TestDetailsDict:
    def test_known_key_findings(self) -> None:
        text = format_verify_text(
            _audit_with(
                {
                    "rule_id": "R",
                    "message": "m",
                    "details": {"findings": ["one", "two"], "total": 2},
                }
            )
        )
        assert "  - one" in text
        assert "  - two" in text

    def test_first_known_key_wins(self) -> None:
        # ``findings`` precedes ``violations`` in the lookup order.
        text = format_verify_text(
            _audit_with(
                {
                    "rule_id": "R",
                    "message": "m",
                    "details": {
                        "findings": ["F"],
                        "violations": ["V"],
                    },
                }
            )
        )
        assert "  - F" in text
        assert "  - V" not in text

    def test_unknown_keys_fallback_to_json(self) -> None:
        text = format_verify_text(
            _audit_with(
                {
                    "rule_id": "R",
                    "message": "m",
                    "details": {"weird_key": 7, "other": "value"},
                }
            )
        )
        assert "weird_key" in text
        assert "value" in text

    def test_unknown_keys_fallback_truncated(self) -> None:
        text = format_verify_text(
            _audit_with(
                {
                    "rule_id": "R",
                    "message": "m",
                    "details": {"weird": "z" * 1000},
                }
            )
        )
        # 500 char ceiling means the literal 1000-char string is cut.
        assert "z" * 1000 not in text
        assert "…" in text


class TestMetadataClusters:
    def test_metadata_clusters_summary(self) -> None:
        clusters = [
            {"signal": "alpha", "members": ["t1", "t2"], "similarity": 0.9},
            {"signal": "alpha", "members": ["t3"], "similarity": 0.8},
            {"signal": "beta", "members": ["t4"], "similarity": 0.7},
        ]
        text = format_verify_text(
            _audit_with(
                {"rule_id": "R", "message": "m", "metadata": {"clusters": clusters}}
            )
        )
        assert "signals:" in text
        assert "alpha=2" in text


class TestFixHint:
    def test_fix_hint_not_truncated(self) -> None:
        long_fix = "y" * 300
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "fix_hint": long_fix})
        )
        fix_lines = [line for line in text.splitlines() if line.startswith("  fix:")]
        assert len(fix_lines) == 1
        assert long_fix in fix_lines[0]
        assert "…" not in fix_lines[0]

    def test_fix_hint_indent(self) -> None:
        text = format_verify_text(
            _audit_with({"rule_id": "R", "message": "m", "fix_hint": "do that"})
        )
        assert "  fix: do that" in text


class TestNoDetail:
    def test_no_detail_when_empty(self) -> None:
        text = format_verify_text(_audit_with({"rule_id": "R", "message": "m"}))
        lines = text.splitlines()
        finding_lines = [line for line in lines if line.startswith("✗ R")]
        assert len(finding_lines) == 1
        idx = lines.index(finding_lines[0])
        rest = lines[idx + 1 :]
        assert all(not line.startswith("  ") for line in rest)


class TestOrdering:
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
