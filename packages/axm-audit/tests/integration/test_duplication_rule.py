"""Tests for DuplicationRule — AST-based copy-paste detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.duplication import DuplicationRule

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


_LARGE_BODY = """
    x = 1
    y = 2
    z = x + y
    w = z * 2
    result = w - x
    return result
"""


def _write_func(path: Path, func_name: str, body: str) -> None:
    """Write a Python file containing a single function."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"def {func_name}():{body}")


@pytest.fixture
def rule() -> DuplicationRule:
    return DuplicationRule()


def test_no_duplicates_text_is_none(tmp_path: Path, rule: DuplicationRule) -> None:
    """2 files, distinct bodies → result.text is None."""
    src = tmp_path / "src"
    _write_func(
        src / "a.py",
        "alpha",
        "\n    return 1\n    x = 2\n    y = 3\n    z = 4\n    w = 5\n",
    )
    _write_func(
        src / "b.py",
        "beta",
        "\n    return 99\n    a = 10\n    b = 20\n    c = 30\n    d = 40\n",
    )
    result = rule.check(tmp_path)
    assert result.text is None


def test_duplicate_text_has_bullets(tmp_path: Path, rule: DuplicationRule) -> None:
    """2 files, identical body → result.text contains bullet and arrow."""
    src = tmp_path / "src"
    _write_func(src / "a.py", "process", _LARGE_BODY)
    _write_func(src / "b.py", "process", _LARGE_BODY)
    result = rule.check(tmp_path)
    assert result.text is not None
    assert "\u2022" in result.text
    assert "\u2192" in result.text


def test_duplicate_text_has_func_name(tmp_path: Path, rule: DuplicationRule) -> None:
    """2 files, identical process() → 'process' appears in text."""
    src = tmp_path / "src"
    _write_func(src / "a.py", "process", _LARGE_BODY)
    _write_func(src / "b.py", "process", _LARGE_BODY)
    result = rule.check(tmp_path)
    assert result.text is not None
    assert "process" in result.text


def test_duplicate_text_has_file_paths(tmp_path: Path, rule: DuplicationRule) -> None:
    """a.py + b.py, identical body → both paths appear in text."""
    src = tmp_path / "src"
    _write_func(src / "a.py", "process", _LARGE_BODY)
    _write_func(src / "b.py", "process", _LARGE_BODY)
    result = rule.check(tmp_path)
    assert result.text is not None
    assert "a.py" in result.text
    assert "b.py" in result.text


def test_no_clones_all_unique(tmp_path: Path, rule: DuplicationRule) -> None:
    """All unique functions → text=None."""
    src = tmp_path / "src"
    for i in range(5):
        body = (
            f"\n    return {i}\n    a = {i + 10}"
            f"\n    b = {i + 20}\n    c = {i + 30}\n    d = {i + 40}\n"
        )
        _write_func(src / f"mod{i}.py", f"func_{i}", body)
    result = rule.check(tmp_path)
    assert result.text is None


def test_twenty_plus_clones_capped(tmp_path: Path, rule: DuplicationRule) -> None:
    """25 clone pairs → text renders exactly 20 lines (capped)."""
    src = tmp_path / "src"
    # 26 files with identical function → 25 clone pairs
    for i in range(26):
        _write_func(src / f"mod{i}.py", "duplicate", _LARGE_BODY)
    result = rule.check(tmp_path)
    assert result.text is not None
    lines = result.text.strip().split("\n")
    assert len(lines) == 20


def test_no_src_dir(tmp_path: Path, rule: DuplicationRule) -> None:
    """Missing src/ → early return from check_src, no text field issue."""
    result = rule.check(tmp_path)
    assert result.passed is True
    assert result.text is None
