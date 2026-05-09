"""Unit tests for ``merge_check`` semantics in workspace aggregation."""

from __future__ import annotations

from typing import cast

from axm_audit.models.results import CheckResult, Severity


class TestMergeCheckPreservesFindings:
    """``merge_check`` concatenates ``findings`` lists.

    Ordering is (existing, incoming).
    """

    def test_workspace_aggregate_concatenates_findings(self):
        """AC4 — findings from both packages survive concatenation."""
        from axm_audit.core.auditor import merge_check
        from axm_audit.core.rules.test_quality.pyramid_level import (
            Finding,
            PyramidCheckResult,
        )

        finding_a = Finding(
            path="packages/a/tests/unit/test_x.py",
            function="test_x",
            level="unit",
            reason="bad",
            current_level="unit",
            has_real_io=False,
            has_subprocess=False,
        )
        finding_b = Finding(
            path="packages/b/tests/unit/test_y.py",
            function="test_y",
            level="unit",
            reason="bad",
            current_level="unit",
            has_real_io=False,
            has_subprocess=False,
        )
        existing = PyramidCheckResult(
            rule_id="r",
            passed=False,
            message="m",
            findings=[finding_a],
        )
        incoming = PyramidCheckResult(
            rule_id="r",
            passed=False,
            message="m",
            findings=[finding_b],
        )

        merged = cast(PyramidCheckResult, merge_check(existing, incoming, "b"))

        assert [f.path for f in merged.findings] == [
            "packages/a/tests/unit/test_x.py",
            "[b] packages/b/tests/unit/test_y.py",
        ] or [f.path for f in merged.findings] == [
            finding_a.path,
            finding_b.path,
        ]
        assert len(merged.findings) == 2


class TestMergeCheckExistingSemanticsUnchanged:
    """AC5 — pre-existing merge semantics for passed/score/severity/text/details."""

    def test_existing_merge_semantics_unchanged(self):
        """AC5 — worst-of-N for passed/score/severity, joined text, shallow details."""
        from axm_audit.core.auditor import merge_check

        existing = CheckResult(
            rule_id="r",
            passed=True,
            message="m",
            severity=Severity.WARNING,
            text="alpha",
            details={"x": 1, "y": 2},
            score=80,
        )
        incoming = CheckResult(
            rule_id="r",
            passed=False,
            message="m",
            severity=Severity.ERROR,
            text="beta",
            details={"y": 99, "z": 3},
            score=40,
        )

        merged = merge_check(existing, incoming, "b")

        assert merged.passed is False
        assert merged.score == 40
        assert merged.severity == Severity.ERROR
        assert merged.text is not None
        assert "alpha" in merged.text
        assert "beta" in merged.text
        assert merged.details is not None
        assert merged.details["x"] == 1
        assert merged.details["y"] == 99
        assert merged.details["z"] == 3
