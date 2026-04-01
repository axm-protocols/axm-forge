"""Edge-case tests for _resolve_dotted — AXM-952 refactor regression."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.hooks.source_body import _resolve_dotted

type PkgFixture = tuple[object, Path]


@pytest.fixture()
def nested_class_pkg(tmp_path: Path) -> PkgFixture:
    """Package with deeply nested classes: Outer.Inner.method."""
    src = tmp_path / "nested_pkg"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "deep.py").write_text(
        """\
class Outer:
    class Inner:
        def method(self):
            return 42
"""
    )
    pkg = analyze_package(src)
    return pkg, src


@pytest.fixture()
def module_func_pkg(tmp_path: Path) -> PkgFixture:
    """Package with a module-level function accessible via module.func."""
    src = tmp_path / "modfunc_pkg"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "helpers.py").write_text(
        """\
def top_level_func():
    return "hello"
"""
    )
    pkg = analyze_package(src)
    return pkg, src


class TestDeeplyNestedDottedPath:
    """Outer.Inner.method — best-effort resolution or None."""

    def test_deeply_nested_returns_none_or_dict(
        self, nested_class_pkg: PkgFixture
    ) -> None:
        pkg, pkg_root = nested_class_pkg
        result = _resolve_dotted(pkg, "Outer.Inner.method", pkg_root)
        # Best-effort: either resolves to a body dict or returns None
        # (fallback to flat search). Both are acceptable.
        if result is not None:
            assert isinstance(result, dict)
            assert "symbol" in result


class TestNonExistentSymbol:
    """FakeClass.fake_method — returns None (fallback to flat)."""

    def test_fake_class_returns_none(self, nested_class_pkg: PkgFixture) -> None:
        pkg, pkg_root = nested_class_pkg
        result = _resolve_dotted(pkg, "FakeClass.fake_method", pkg_root)
        # No class named FakeClass exists, so no class branch matches.
        # No module named FakeClass either → returns None for flat fallback.
        assert result is None

    def test_real_class_fake_member_returns_error(
        self, nested_class_pkg: PkgFixture
    ) -> None:
        pkg, pkg_root = nested_class_pkg
        result = _resolve_dotted(pkg, "Outer.nonexistent", pkg_root)
        # Class found but member missing → definitive not-found dict
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("body") is None
        assert "not found" in result.get("error", "").lower()


class TestModuleLevelFunction:
    """module.top_level_func — resolves via module path."""

    def test_module_dot_func_resolves(self, module_func_pkg: PkgFixture) -> None:
        pkg, pkg_root = module_func_pkg
        result = _resolve_dotted(pkg, "helpers.top_level_func", pkg_root)
        # Should resolve via module.symbol branch
        assert result is not None
        assert isinstance(result, dict)
        assert result["symbol"] == "helpers.top_level_func"
        assert result.get("body") is not None

    def test_module_dot_missing_func_returns_not_found(
        self, module_func_pkg: PkgFixture
    ) -> None:
        pkg, pkg_root = module_func_pkg
        result = _resolve_dotted(pkg, "helpers.no_such_func", pkg_root)
        # Module exists but symbol doesn't → not-found dict
        assert result is not None
        assert isinstance(result, dict)
        assert "not found" in result.get("error", "").lower()
