from __future__ import annotations

import pytest

from axm_audit.core.rules.complexity import ComplexityRule


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


def _make_offenders(
    items: list[tuple[str, str, int]],
) -> list[dict[str, str | int]]:
    """Build offender dicts from (file, function, cc) tuples."""
    return [{"file": f, "function": fn, "cc": cc} for f, fn, cc in items]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBuildResultTextFormat:
    """AC1: text lines use format `\u2022 {file}:{function} {cc}`."""

    def test_build_result_text_format(self, rule: ComplexityRule) -> None:
        offenders = _make_offenders(
            [
                ("src/mod.py", "foo", 15),
                ("src/mod.py", "bar", 12),
                ("src/util.py", "baz", 10),
            ]
        )
        result = rule._build_result(3, offenders)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        for line in lines:
            # No leading spaces, no arrow, no (cc=) wrapper
            assert not line.startswith(" ")
            assert "\u2192" not in line
            assert "(cc=" not in line
            # Matches \u2022 {file}:{function} {cc}
            assert line.startswith("\u2022 ")
            parts = line[2:].split(" ")
            assert len(parts) == 2
            assert ":" in parts[0]

    def test_build_result_empty_offenders(self, rule: ComplexityRule) -> None:
        """AC2: text=None when top_offenders is empty."""
        result = rule._build_result(0, [])
        assert result.text is None

    def test_build_result_details_unchanged(self, rule: ComplexityRule) -> None:
        """AC3: details dict has correct keys and values."""
        offenders = _make_offenders(
            [
                ("a.py", "f1", 15),
                ("b.py", "f2", 12),
                ("c.py", "f3", 10),
            ]
        )
        result = rule._build_result(3, offenders)

        assert result.details is not None
        assert "high_complexity_count" in result.details
        assert "top_offenders" in result.details
        assert "score" in result.details
        assert result.details["high_complexity_count"] == 3
        assert result.details["score"] == 70
        # top_offenders sorted descending by cc
        ccs = [o["cc"] for o in result.details["top_offenders"]]
        assert ccs == sorted(ccs, reverse=True)


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
        result = rule._build_result(3, offenders)

        assert result.text is not None
        for line in result.text.split("\n"):
            # file:function pattern, no arrows or (cc=)
            assert ":" in line
            assert "\u2192" not in line
            assert "(cc=" not in line


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBuildResultEdgeCases:
    def test_class_method_preserved(self, rule: ComplexityRule) -> None:
        """Class method shows as file.py:ClassName.method cc."""
        offenders = _make_offenders(
            [
                ("src/service.py", "MyClass.process", 20),
            ]
        )
        result = rule._build_result(1, offenders)

        assert result.text is not None
        assert "src/service.py:MyClass.process 20" in result.text

    def test_single_offender_no_trailing_newline(self, rule: ComplexityRule) -> None:
        """Single offender produces one line with no trailing newline."""
        offenders = _make_offenders([("a.py", "heavy", 25)])
        result = rule._build_result(1, offenders)

        assert result.text is not None
        assert "\n" not in result.text
        assert result.text == "\u2022 a.py:heavy 25"
