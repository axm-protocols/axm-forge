from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

pytestmark = pytest.mark.integration


def _make_function_with_cc(name: str, n_branches: int) -> str:
    """Build a Python function with cyclomatic complexity == ``n_branches`` + 1."""
    lines = [f"def {name}(x):"]
    for i in range(n_branches):
        lines.append(f"    if x == {i}:")
        lines.append("        return 0")
    lines.append("    return 1")
    return "\n".join(lines) + "\n"


@pytest.fixture
def project_with_function(tmp_path: Path):
    def _build(name: str, n_branches: int) -> Path:
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        module = src / f"{name}.py"
        module.write_text(_make_function_with_cc(name, n_branches), encoding="utf-8")
        return tmp_path

    return _build


def test_cc_equals_10_grade_b_passes(project_with_function):
    """AC1: CC=10 (grade B) must NOT count as a high-complexity violation."""
    project = project_with_function("mod_b", n_branches=9)

    rule = ComplexityRule()
    result = rule.check(project)

    assert result.details["high_complexity_count"] == 0


def test_cc_equals_11_grade_c_flagged(project_with_function):
    """AC2: CC=11 (grade C) must count as a violation with rank='C'."""
    project = project_with_function("mod_c", n_branches=10)

    rule = ComplexityRule()
    result = rule.check(project)

    assert result.details["high_complexity_count"] == 1
    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "C"


def test_high_grade_d_includes_rank(project_with_function):
    """AC3, AC5: a CC>=21 function reports rank='D' in offenders."""
    project = project_with_function("mod_d", n_branches=24)

    rule = ComplexityRule()
    result = rule.check(project)

    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "D"
    assert offenders[0]["cc"] >= 21


def test_top_offenders_have_rank_key(tmp_path: Path):
    """AC5: every offender entry exposes a 'rank' key alongside 'cc'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(_make_function_with_cc("a", 11), encoding="utf-8")
    (src / "b.py").write_text(_make_function_with_cc("b", 14), encoding="utf-8")

    rule = ComplexityRule()
    result = rule.check(tmp_path)

    offenders = result.details["top_offenders"]
    assert len(offenders) == 2
    assert all("rank" in o for o in offenders)
    assert all("cc" in o for o in offenders)
