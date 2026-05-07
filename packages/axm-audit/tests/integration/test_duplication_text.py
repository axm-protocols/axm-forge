from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.duplication import DuplicationRule

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


# ── Unit tests ──────────────────────────────────────────────────────


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


# ── Edge cases ──────────────────────────────────────────────────────


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
