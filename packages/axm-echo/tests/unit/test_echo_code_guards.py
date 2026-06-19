"""Unit tests for ``EchoCodeTool`` input guards.

These exercise the pre-flight validation branches that short-circuit
*before* any corpus access, so they need no filesystem and stay at the
unit level. ``tools.py`` is mirror-exempt, hence the dedicated guard file.
"""

from __future__ import annotations

import pytest

from axm_echo.tools import EchoCodeTool


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"backend": "bogus"}, "invalid backend"),
        ({"threshold": 1.5}, "cosine in [0.0, 1.0]"),
        ({"threshold": -0.1}, "cosine in [0.0, 1.0]"),
        ({"top_n": 0}, "top_n must be >= 1"),
        ({"max_cluster_size": 0}, "max_cluster_size must be >= 1"),
    ],
)
def test_invalid_input_returns_error_result(
    kwargs: dict[str, object], needle: str
) -> None:
    result = EchoCodeTool().execute(**kwargs)
    assert result.success is False
    assert needle in (result.error or "").lower()
