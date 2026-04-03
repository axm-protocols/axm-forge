from __future__ import annotations

from axm_git.hooks.preflight import _truncate_diff


def test_truncate_diff_under_limit() -> None:
    """10 lines with max=200 returns all lines stripped."""
    stdout = "\n".join(f"line {i}" for i in range(10))
    result = _truncate_diff(stdout, max_lines=200)
    assert result == stdout.strip()


def test_truncate_diff_over_limit() -> None:
    """300 lines with max=200 returns first 200 lines."""
    lines = [f"line {i}" for i in range(300)]
    stdout = "\n".join(lines)
    result = _truncate_diff(stdout, max_lines=200)
    expected = "\n".join(lines[:200])
    assert result == expected


def test_truncate_diff_zero_lines() -> None:
    """max_lines=0 returns empty string (user disables diff)."""
    stdout = "\n".join(f"line {i}" for i in range(10))
    result = _truncate_diff(stdout, max_lines=0)
    assert result == ""
