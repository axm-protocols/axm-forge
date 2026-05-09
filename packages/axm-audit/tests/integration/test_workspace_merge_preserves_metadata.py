"""Integration tests: workspace aggregation must preserve metadata + findings.

Covers AC3, AC4, AC5 of AXM-1714. The audit aggregator merges per-package
``CheckResult``s by ``rule_id``; before this fix it dropped ``metadata`` and
``findings`` from packages other than the first one to fire a given rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from axm_audit.models.results import CheckResult, Severity

pytestmark = pytest.mark.integration


def _make_workspace(tmp_path: Path) -> Path:
    """Build a fake workspace with two packages on the filesystem."""
    root = tmp_path / "ws"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
        encoding="utf-8",
    )
    pkgs_dir = root / "packages"
    pkgs_dir.mkdir()
    for name in ("a", "b"):
        pkg = pkgs_dir / name
        (pkg / "src" / f"pkg_{name}").mkdir(parents=True)
        (pkg / "src" / f"pkg_{name}" / "__init__.py").write_text(
            '"""Minimal package."""\n', encoding="utf-8"
        )
        (pkg / "pyproject.toml").write_text(
            f'[project]\nname = "pkg-{name}"\nversion = "0.0.1"\n',
            encoding="utf-8",
        )
    return root


class TestWorkspaceAggregateUnionsMetadata:
    """Public API: ``audit_project`` on a workspace unions metadata."""

    def test_workspace_aggregate_unions_per_package_verdicts(
        self, tmp_path, monkeypatch
    ):
        """AC3 — verdicts from every package survive workspace aggregation."""
        from axm_audit.core import auditor as auditor_mod
        from axm_audit.models.results import AuditResult

        ws = _make_workspace(tmp_path)

        original = auditor_mod.audit_project

        def fake_audit_project(project_path, category=None, quick=False):
            if project_path == ws:
                return original(project_path, category=category, quick=quick)
            pkg_name = project_path.name
            return AuditResult(
                project_path=str(project_path),
                checks=[
                    CheckResult(
                        rule_id="verdict_rule",
                        passed=True,
                        message="ok",
                        severity=Severity.INFO,
                        metadata={"verdicts": [f"from_{pkg_name}"]},
                    )
                ],
            )

        monkeypatch.setattr(auditor_mod, "audit_project", fake_audit_project)

        result = original(ws)

        merged = next(c for c in result.checks if c.rule_id == "verdict_rule")
        assert "from_a" in merged.metadata["verdicts"]
        assert "from_b" in merged.metadata["verdicts"]


class TestMergeCheckPreservesFindings:
    """``_merge_check`` concatenates ``findings`` lists.

    Ordering is (existing, incoming).
    """

    def test_workspace_aggregate_concatenates_findings(self):
        """AC4 — findings from both packages survive concatenation."""
        from axm_audit.core.auditor import _merge_check
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

        merged = cast(PyramidCheckResult, _merge_check(existing, incoming, "b"))

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
        from axm_audit.core.auditor import _merge_check

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

        merged = _merge_check(existing, incoming, "b")

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
