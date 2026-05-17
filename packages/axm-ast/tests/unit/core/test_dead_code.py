"""Unit tests mirroring src/axm_ast/core/dead_code.py."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_ns_pkg(modules: list[object]) -> MagicMock:
    """Create a minimal PackageInfo-like mock."""
    pkg = MagicMock()
    pkg.modules = modules
    return pkg


class TestLazyImportNamespaceDetectionUnit:
    """Pure unit cases (no filesystem I/O)."""

    def test_empty_package_returns_empty_set(self) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg = _make_ns_pkg([])
        result = _find_namespace_modules(pkg)

        assert result == set()
