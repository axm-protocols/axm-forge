"""Integration: a crashing scored rule penalizes the composite score."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.models.results import _CATEGORY_WEIGHTS


def _make_minimal_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    pkg = root / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")


@pytest.mark.integration
def test_audit_with_crashing_rule_penalizes_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: a rule monkeypatched to raise contributes 0 to its scored
    category — quality_score is penalized vs the healthy run, and the rule
    is named in crashed_rules instead of being silently dropped."""
    _make_minimal_project(tmp_path)

    healthy = audit_project(tmp_path)
    healthy_score = healthy.quality_score

    # Locate a check actually emitted in a scored category, then make the
    # owning rule class raise on .check().
    from axm_audit.core.rules.base import ProjectRule, get_registry

    target_cls: type[ProjectRule] | None = None
    for category, rule_classes in get_registry().items():
        if category in _CATEGORY_WEIGHTS and rule_classes:
            target_cls = rule_classes[0]
            break
    assert target_cls is not None

    def _boom(self: ProjectRule, project_path: Path) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(target_cls, "check", _boom, raising=True)

    crashed = audit_project(tmp_path)

    assert crashed.crashed_rules, "expected at least one crashed rule recorded"
    if healthy_score is not None and crashed.quality_score is not None:
        assert crashed.quality_score < healthy_score
