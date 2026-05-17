"""Split from ``test_cache_invalidation.py``."""

from pathlib import Path

import pytest

from axm_ast.core.cache import get_package

FIXTURES = Path(__file__).parents[1] / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


@pytest.mark.integration
def test_get_package_returns_package_info() -> None:
    result = get_package(SAMPLE_PKG)
    assert result.name == "sample_pkg"
    assert len(result.modules) >= 1
