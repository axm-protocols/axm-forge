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
    find_definition,
    find_type_refs,
    score_impact,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
)

SELF_PKG = Path(__file__).resolve().parents[3] / "src" / "axm_ast"


# ────────────────────────────────────────────────────────────────────────────
# score_impact — dict inputs
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("result", "expected_score"),
    [
        pytest.param(
            {
                "callers": [1, 2, 3, 4, 5],
                "reexports": ["__init__"],
                "affected_modules": ["a", "b", "c"],
            },
            "HIGH",
            id="high_many_callers_and_reexport",
        ),
        pytest.param(
            {
                "callers": [1, 2],
                "reexports": [],
                "affected_modules": ["a"],
            },
            "MEDIUM",
            id="medium_some_callers",
        ),
        pytest.param(
            {
                "callers": [],
                "reexports": [],
                "affected_modules": [],
            },
            "LOW",
            id="low_no_signal",
        ),
        pytest.param(
            {
                "callers": [],
                "reexports": [],
                "affected_modules": [],
                "git_coupled": [],
                "type_refs": [
                    {"function": f"fn{i}", "module": "mod", "line": i} for i in range(5)
                ],
            },
            "HIGH",
            id="high_via_5_type_refs",
        ),
        pytest.param(
            {
                "callers": [],
                "reexports": [],
                "affected_modules": [],
                "git_coupled": [],
                "type_refs": [
                    {"function": "fn1", "module": "mod", "line": 1},
                    {"function": "fn2", "module": "mod", "line": 2},
                ],
            },
            "MEDIUM",
            id="medium_via_2_type_refs",
        ),
        pytest.param(
            {
                "callers": [],
                "reexports": [],
                "affected_modules": [],
                "git_coupled": [],
                "type_refs": [],
            },
            "LOW",
            id="low_no_type_refs",
        ),
    ],
)
def test_score_impact_from_dict(result: dict[str, Any], expected_score: str) -> None:
    """score_impact returns expected severity from raw dict input."""
    assert score_impact(result) == expected_score


# ────────────────────────────────────────────────────────────────────────────
# score_impact — type_refs contribution
# ────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────
# score_impact — ImpactReport inputs
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("caller_count", "expected_score"),
    [
        pytest.param(5, "HIGH", id="high_above_threshold"),
        pytest.param(1, "LOW", id="low_below_medium"),
    ],
)
def test_score_impact_from_caller_count(caller_count: int, expected_score: str) -> None:
    report = ImpactReport(callers=[{}] * caller_count)
    assert score_impact(report) == expected_score


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


# ────────────────────────────────────────────────────────────────────────────
# find_definition — homonym disambiguation (AXM-1884 / F3)
# ────────────────────────────────────────────────────────────────────────────


def _fn(name: str, line: int) -> FunctionInfo:
    return FunctionInfo(name=name, line_start=line, line_end=line + 1)


def _mod(
    rel: str, *, functions: list[FunctionInfo], classes: list[ClassInfo]
) -> ModuleInfo:
    return ModuleInfo(path=Path("/pkg") / rel, functions=functions, classes=classes)


def _pkg(*modules: ModuleInfo) -> PackageInfo:
    return PackageInfo(name="pkg", root=Path("/pkg"), modules=list(modules))


def test_find_definition_homonym_surfaces_ambiguity() -> None:
    """AC1: a plain name matching >1 top-level def surfaces the ambiguity.

    Mirrors ``_inspect_symbol``'s ``"Multiple symbols match '...': ..."``
    message instead of silently returning the first homonym.
    """
    pkg = _pkg(
        _mod("alpha.py", functions=[_fn("helper", 10)], classes=[]),
        _mod("beta.py", functions=[_fn("helper", 20)], classes=[]),
    )
    with pytest.raises(ValueError, match="Multiple symbols match 'helper'") as exc:
        find_definition(pkg, "helper")
    message = str(exc.value)
    # Both candidates surfaced as dotted module paths.
    assert "alpha.helper" in message
    assert "beta.helper" in message


def test_find_definition_unique_name_resolves() -> None:
    """AC2: a unique plain name resolves exactly as before (no change)."""
    pkg = _pkg(
        _mod("alpha.py", functions=[_fn("solo", 7)], classes=[]),
        _mod("beta.py", functions=[_fn("other", 3)], classes=[]),
    )
    result = find_definition(pkg, "solo")
    assert result is not None
    assert result["module"] == "alpha"
    assert result["line"] == 7
    assert result["kind"] == "function"


def test_find_definition_dotted_unaffected() -> None:
    """AC3: the dotted ``ClassName.method`` path is unaffected."""
    cls = ClassInfo(
        name="Widget",
        line_start=1,
        line_end=20,
        methods=[_fn("render", 5)],
    )
    pkg = _pkg(_mod("ui.py", functions=[], classes=[cls]))
    result = find_definition(pkg, "Widget.render")
    assert result is not None
    # Resolved via the dotted (class-body) path, not the plain-name path.
    assert result["module"] == "ui"
    assert result["line"] == 5
