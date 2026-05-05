"""Tests for DuplicationRule — AST-based copy-paste detection."""

from __future__ import annotations

from pathlib import Path

import pytest

_DISTINCT_A = (
    "def add(a: int, b: int) -> int:\n"
    "    result = a + b\n"
    "    if result > 0:\n"
    "        return result\n"
    "    elif result < 0:\n"
    "        return -result\n"
    "    return 0\n"
)
_DISTINCT_B = (
    "def multiply(a: int, b: int) -> int:\n"
    "    result = a * b\n"
    "    if result > 100:\n"
    "        return 100\n"
    "    elif result < -100:\n"
    "        return -100\n"
    "    return result\n"
)
_TINY = "def tiny(x: int) -> int:\n    return x + 1\n"


class TestDuplicationRule:
    """Tests for DuplicationRule (AST structure hashing)."""

    @pytest.mark.parametrize(
        ("a_src", "b_src"),
        [
            pytest.param(_DISTINCT_A, _DISTINCT_B, id="distinct_bodies"),
            pytest.param(_TINY, _TINY, id="identical_but_below_min_lines"),
        ],
    )
    def test_no_duplicates_detected(
        self, tmp_path: Path, a_src: str, b_src: str
    ) -> None:
        """Distinct or sub-threshold function bodies should pass without duplicates."""
        from axm_audit.core.rules.duplication import DuplicationRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text(a_src)
        (src / "b.py").write_text(b_src)

        rule = DuplicationRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["dup_count"] == 0

    def test_detects_duplicate_functions(self, tmp_path: Path) -> None:
        """Identical function bodies in different files should be detected."""
        from axm_audit.core.rules.duplication import DuplicationRule

        body = (
            "def process(x: int) -> int:\n"
            "    if x > 0:\n"
            "        result = x * 2\n"
            "        if result > 100:\n"
            "            return 100\n"
            "        return result\n"
            "    return 0\n"
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text(body)
        (src / "b.py").write_text(body)

        rule = DuplicationRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["dup_count"] >= 1
        assert len(result.details["clones"]) >= 1
        assert result.fix_hint is not None

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """No src/ directory should pass gracefully."""
        from axm_audit.core.rules.duplication import DuplicationRule

        rule = DuplicationRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.score == 100

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_DUPLICATION."""
        from axm_audit.core.rules.duplication import DuplicationRule

        rule = DuplicationRule()
        assert rule.rule_id == "ARCH_DUPLICATION"

    def test_score_decreases_with_more_duplicates(self, tmp_path: Path) -> None:
        """Score should decrease proportionally to duplicate count."""
        from axm_audit.core.rules.duplication import DuplicationRule

        # Same function name + body across all files → identical AST
        body = (
            "def process(x: int) -> int:\n"
            "    if x > 0:\n"
            "        result = x * 2\n"
            "        if result > 100:\n"
            "            return 100\n"
            "        return result\n"
            "    return 0\n"
        )
        src = tmp_path / "src"
        src.mkdir()
        # Create 4 files with identical body → 3 clone pairs
        for i in range(4):
            (src / f"mod_{i}.py").write_text(body)

        rule = DuplicationRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.score is not None
        assert result.score < 100
        assert result.details["dup_count"] >= 3
