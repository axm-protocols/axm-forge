"""Split from ``test_cache_invalidation.py``."""

from pathlib import Path

import pytest

from axm_ast.core.cache import clear_cache, get_package

FIXTURES = Path(__file__).parents[1] / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


@pytest.mark.integration
def test_clear_cache_then_get() -> None:
    """get_package → clear_cache → get_package re-parses correctly."""
    first = get_package(SAMPLE_PKG)
    clear_cache()
    second = get_package(SAMPLE_PKG)
    assert first is not second
    assert first.name == second.name
