"""Unit tests for axm_ast.core.impact.

Covers score_impact (dict + ImpactReport inputs), ImpactReport validation,
and find_type_refs (dogfooded against the axm-ast source tree).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import (
    REEXPORT_WEIGHT,
    ImpactReport,
    find_type_refs,
    score_impact,
)

SELF_PKG = Path(__file__).resolve().parents[3] / "src" / "axm_ast"


# ────────────────────────────────────────────────────────────────────────────
# score_impact — dict inputs
# ────────────────────────────────────────────────────────────────────────────


class TestScoreImpactFromDict:
    """Test impact scoring with raw dict inputs."""

    def test_high_impact(self) -> None:
        """Many callers + re-exported = HIGH."""
        result = {
            "callers": [1, 2, 3, 4, 5],
            "reexports": ["__init__"],
            "affected_modules": ["a", "b", "c"],
        }
        assert score_impact(result) == "HIGH"

    def test_low_impact(self) -> None:
        """No callers, no re-exports = LOW."""
        result: dict[str, list[str | int]] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
        }
        assert score_impact(result) == "LOW"

    def test_medium_impact(self) -> None:
        """Some callers = MEDIUM."""
        result = {
            "callers": [1, 2],
            "reexports": [],
            "affected_modules": ["a"],
        }
        assert score_impact(result) == "MEDIUM"


# ────────────────────────────────────────────────────────────────────────────
# score_impact — type_refs contribution
# ────────────────────────────────────────────────────────────────────────────


class TestScoreImpactWithTypeRefs:
    """Pure dict-driven score_impact tests with type_refs (no I/O)."""

    def test_impact_score_with_types(self) -> None:
        """AC3: Score is HIGH when type is used by 5+ functions."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": f"fn{i}", "module": "mod", "line": i} for i in range(5)
            ],
        }
        assert score_impact(result) == "HIGH"

    def test_score_medium_with_type_refs(self) -> None:
        """Score MEDIUM with 2 type refs and no callers."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": "fn1", "module": "mod", "line": 1},
                {"function": "fn2", "module": "mod", "line": 2},
            ],
        }
        assert score_impact(result) == "MEDIUM"

    def test_score_low_without_type_refs(self) -> None:
        """Score LOW with no type refs and no callers."""
        result: dict[str, Any] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [],
        }
        assert score_impact(result) == "LOW"


# ────────────────────────────────────────────────────────────────────────────
# score_impact — ImpactReport inputs
# ────────────────────────────────────────────────────────────────────────────


def test_score_impact_returns_high_above_threshold() -> None:
    report = ImpactReport(callers=[{}] * 5)
    assert score_impact(report) == "HIGH"


def test_score_impact_returns_low_below_medium() -> None:
    report = ImpactReport(callers=[{}] * 1)
    assert score_impact(report) == "LOW"


def test_score_impact_reexport_double_weight() -> None:
    one_reexport = ImpactReport(reexports=["some.module"])
    equivalent_callers = ImpactReport(callers=[{}] * REEXPORT_WEIGHT)
    assert score_impact(one_reexport) == score_impact(equivalent_callers)


# ────────────────────────────────────────────────────────────────────────────
# ImpactReport — schema validation
# ────────────────────────────────────────────────────────────────────────────


def test_impact_report_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ImpactReport(unknown_field=[])  # type: ignore[call-arg]


# ────────────────────────────────────────────────────────────────────────────
# find_type_refs — dogfooded against axm-ast itself
# ────────────────────────────────────────────────────────────────────────────


class TestTypeRefsDogfood:
    """Run type ref analysis on axm-ast itself."""

    def test_type_refs_dogfood(self) -> None:
        """PackageInfo is widely used in params/returns across axm-ast."""
        pkg = analyze_package(SELF_PKG)
        refs = find_type_refs(pkg, "PackageInfo")
        assert len(refs) >= 1, f"Expected ≥1 type refs to PackageInfo, got {len(refs)}"
        # Should include both param and return refs.
        ref_types = {r["ref_type"] for r in refs}
        assert "param" in ref_types
