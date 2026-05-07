"""Integration tests for complexity text rendering."""

from __future__ import annotations

import pytest

from axm_audit.core.rules.complexity import ComplexityRule


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


def _rank_for(cc: int) -> str:
    """Mirror radon's grade mapping.

    A 1-5, B 6-10, C 11-20, D 21-30, E 31-40, F 41+.
    """
    if cc <= 5:
        return "A"
    if cc <= 10:
        return "B"
    if cc <= 20:
        return "C"
    if cc <= 30:
        return "D"
    if cc <= 40:
        return "E"
    return "F"


def _make_offenders(
    items: list[tuple[str, str, int]],
) -> list[dict[str, str | int]]:
    """Build offender dicts from (file, function, cc) tuples (cog=0, reason='cc')."""
    return [
        {
            "file": f,
            "function": fn,
            "cc": cc,
            "rank": _rank_for(cc),
            "cognitive": 0,
            "reason": "cc",
        }
        for f, fn, cc in items
    ]


class TestComplexityCheckTextRendering:
    """Functional: text lines from check() contain file:function pattern."""

    def test_complexity_check_text_rendering(
        self, rule: ComplexityRule, tmp_path: object
    ) -> None:
        """Simulate _build_result via direct call with realistic data."""
        offenders = _make_offenders(
            [
                ("src/engine.py", "run_pipeline", 22),
                ("src/parser.py", "parse_tokens", 18),
                ("src/validator.py", "validate_all", 14),
            ]
        )
        result = rule._build_result(offenders)

        assert result.text is not None
        for line in result.text.split("\n"):
            assert ":" in line
            assert "→" not in line
            assert "cc=" in line
