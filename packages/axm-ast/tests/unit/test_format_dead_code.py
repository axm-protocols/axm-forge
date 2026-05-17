"""Split from ``test_dead_code.py``."""

from axm_ast.core.dead_code import format_dead_code


def test_format_empty() -> None:
    """Empty results → clean message."""
    assert format_dead_code([]) == "\u2705 No dead code detected."
