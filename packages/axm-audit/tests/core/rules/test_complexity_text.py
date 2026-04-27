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


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBuildResultTextFormat:
    """Text format: `• {file}:{function} cc={cc} ({rank}) cog={cog} [{reason}]`."""

    def test_build_result_text_format(self, rule: ComplexityRule) -> None:
        offenders = _make_offenders(
            [
                ("src/mod.py", "foo", 15),
                ("src/mod.py", "bar", 12),
                ("src/util.py", "baz", 11),
            ]
        )
        result = rule._build_result(offenders)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        for line in lines:
            assert not line.startswith(" ")
            assert "→" not in line
            assert line.startswith("• ")
            assert "cc=" in line
            assert "cog=" in line
            assert "[" in line and "]" in line

    def test_build_result_empty_offenders(self, rule: ComplexityRule) -> None:
        """text=None when offenders is empty."""
        result = rule._build_result([])
        assert result.text is None

    def test_build_result_details_unchanged(self, rule: ComplexityRule) -> None:
        """details dict has correct keys and values."""
        offenders = _make_offenders(
            [
                ("a.py", "f1", 15),
                ("b.py", "f2", 12),
                ("c.py", "f3", 11),
            ]
        )
        result = rule._build_result(offenders)

        assert result.details is not None
        assert "high_complexity_count" in result.details
        assert "top_offenders" in result.details
        assert "score" in result.details
        assert result.details["high_complexity_count"] == 3
        assert result.details["score"] == 70
        # top_offenders sorted descending by max(cc, cognitive)
        keys = [
            max(int(o["cc"]), int(o["cognitive"]))
            for o in result.details["top_offenders"]
        ]
        assert keys == sorted(keys, reverse=True)


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBuildResultEdgeCases:
    def test_class_method_preserved(self, rule: ComplexityRule) -> None:
        """Class method shows as file.py:ClassName.method cc=N (rank) ..."""
        offenders = _make_offenders(
            [
                ("src/service.py", "MyClass.process", 20),
            ]
        )
        result = rule._build_result(offenders)

        assert result.text is not None
        assert "src/service.py:MyClass.process" in result.text
        assert "cc=20" in result.text
        assert "(C)" in result.text

    def test_single_offender_no_trailing_newline(self, rule: ComplexityRule) -> None:
        """Single offender produces one line with no trailing newline."""
        offenders = _make_offenders([("a.py", "heavy", 25)])
        result = rule._build_result(offenders)

        assert result.text is not None
        assert "\n" not in result.text
        assert result.text == "• a.py:heavy cc=25 (D) cog=0 [cc]"
