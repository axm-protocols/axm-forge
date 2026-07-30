from __future__ import annotations

from axm_smelt.strategies.fences import FENCED_BLOCK_RE, fenced_line_indices


def test_quad_fence_not_closed_by_inner_triple() -> None:
    text = "````\n```\ninner\n```\n````\nafter"
    indices = fenced_line_indices(text)
    assert indices == {0, 1, 2, 3, 4}
    assert 5 not in indices


def test_triple_fence_lines_detected() -> None:
    text = "```\ncode\n```\nafter"
    assert fenced_line_indices(text) == {0, 1, 2}


def test_no_fence_returns_empty_set() -> None:
    assert fenced_line_indices("plain\ntext") == set()


def test_fenced_block_re_matches_quad_backtick() -> None:
    assert FENCED_BLOCK_RE.match("````\nx\n````") is not None
