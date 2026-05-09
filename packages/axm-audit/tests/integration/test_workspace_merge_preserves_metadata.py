"""Integration tests: workspace aggregation must preserve metadata + findings.

Covers AC3, AC4, AC5 of AXM-1714. The audit aggregator merges per-package
``CheckResult``s by ``rule_id``; before this fix it dropped ``metadata`` and
``findings`` from packages other than the first one to fire a given rule.
"""

from __future__ import annotations

from pathlib import Path

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
