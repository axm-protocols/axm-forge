"""Integration tests for axm_audit.core.fix.cst_rewrite import-index cache."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import (
    _PROJECT_IMPORT_INDEX_CACHE,
    invalidate_import_index,
    resolve_import_for_symbol,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def _clean_import_index_cache(tmp_path: Path) -> Iterator[None]:
    """Ensure the cache starts empty for *tmp_path*."""
    invalidate_import_index(tmp_path)
    yield
    invalidate_import_index(tmp_path)


def test_import_index_cache_returns_same_object_on_hit(
    tmp_path: Path, _clean_import_index_cache: None
) -> None:
    """AC7: consecutive resolver calls hit the cache and return same value."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def foo():\n    pass\n")

    first = resolve_import_for_symbol(tmp_path, "foo")
    assert tmp_path in _PROJECT_IMPORT_INDEX_CACHE
    second = resolve_import_for_symbol(tmp_path, "foo")
    assert first == second


def test_import_index_cache_rebuilt_after_invalidate(
    tmp_path: Path, _clean_import_index_cache: None
) -> None:
    """AC7: invalidate_import_index drops the cache so next call refreshes."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def foo():\n    pass\n")

    resolve_import_for_symbol(tmp_path, "foo")
    assert tmp_path in _PROJECT_IMPORT_INDEX_CACHE

    invalidate_import_index(tmp_path)
    assert tmp_path not in _PROJECT_IMPORT_INDEX_CACHE

    # Extend the package; resolver should pick up the new symbol after rebuild.
    (pkg / "mod2.py").write_text("def bar():\n    pass\n")
    resolved = resolve_import_for_symbol(tmp_path, "bar")
    assert resolved is not None
