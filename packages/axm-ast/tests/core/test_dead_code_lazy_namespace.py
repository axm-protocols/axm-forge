"""Tests for lazy namespace import detection in _find_namespace_modules.

Ticket: AXM-1225 — _find_namespace_modules misses lazy imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(path: Path, *, imports: list[object] | None = None) -> MagicMock:
    """Create a minimal ModuleInfo-like mock."""
    mod = MagicMock()
    mod.path = path
    mod.imports = imports or []
    return mod


def _make_import(
    *, module: str | None = None, names: list[str] | None = None
) -> MagicMock:
    """Create a minimal ImportInfo-like mock."""
    imp = MagicMock()
    imp.module = module
    imp.names = names or []
    return imp


def _make_pkg(modules: list[object]) -> MagicMock:
    """Create a minimal PackageInfo-like mock."""
    pkg = MagicMock()
    pkg.modules = modules
    return pkg


def _write_source(path: Path, source: str) -> Path:
    """Write a Python source file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestLazyImportNamespaceModuleNotDead:
    """Module A has a function-body `from mypkg import utils`;
    B (utils.py) has public func() with no direct callers.
    func should NOT be in dead names."""

    def test_lazy_import_namespace_module_not_dead(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        # Module A: has a lazy import of utils inside a function body
        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg import utils\n    utils.func()\n",
        )

        # Module B: utils.py with a public function
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 42\n",
        )

        # Module A has NO module-level imports of utils
        mod_a = _make_module(mod_a_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        # utils.py should be detected as namespace module via the lazy import
        assert mod_b_path in result


class TestLazyImportPrivateFnStillDead:
    """Same setup; B has _helper() with no callers.
    _helper should still be in dead names (private fn exemption
    is handled elsewhere, but the module IS namespace-imported)."""

    def test_lazy_import_private_fn_still_dead(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg import utils\n    utils.func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def _helper():\n    return 1\n\ndef func():\n    return _helper()\n",
        )

        mod_a = _make_module(mod_a_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        # utils.py IS detected as namespace (the lazy import brings it in).
        # Whether _helper is dead is decided by _scan_functions, not here.
        # This test verifies the module is still recognized as namespace.
        assert mod_b_path in result


class TestLazyImportNotAModuleStillDead:
    """Module A has `from mypkg.utils import func` inside function body
    (imports symbol, not module). func has no callers → should remain dead."""

    def test_lazy_import_not_a_module_still_dead(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        # A imports a SYMBOL from utils, not the module itself
        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg.utils import func\n    func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 42\n",
        )

        mod_a = _make_module(mod_a_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        # "func" is a symbol name, not a module stem → utils.py NOT namespace
        assert mod_b_path not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBothModuleLevelAndLazyNamespaceImport:
    """Module A imports B at module level, Module C imports B lazily.
    B detected as namespace (either path suffices)."""

    def test_both_module_level_and_lazy(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "mod_a.py",
            "from mypkg import helpers\nhelpers.run()\n",
        )
        mod_c_path = _write_source(
            pkg_dir / "mod_c.py",
            "def work():\n    from mypkg import helpers\n    helpers.run()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "helpers.py",
            "def run():\n    pass\n",
        )

        # A has module-level import of helpers
        imp_a = _make_import(module="mypkg", names=["helpers"])
        mod_a = _make_module(mod_a_path, imports=[imp_a])
        # C has NO module-level import (lazy only)
        mod_c = _make_module(mod_c_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_c, mod_b])

        result = _find_namespace_modules(pkg)

        # helpers.py is namespace via module-level (A) AND lazy (C)
        assert mod_b_path in result


class TestLazyImportWithAlias:
    """`from mypkg import utils as u` inside function body.
    utils.py still detected as namespace module (alias doesn't matter)."""

    def test_lazy_import_with_alias(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def work():\n    from mypkg import utils as u\n    u.func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        mod_a = _make_module(mod_a_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        # "utils" is the original name (before alias) → matches mod_stems
        assert mod_b_path in result


class TestLazyImportInNestedFunction:
    """`from mypkg import utils` inside a nested function.
    Still detected — any function body counts."""

    def test_lazy_import_in_nested_function(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import _find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            (
                "def outer():\n"
                "    def inner():\n"
                "        from mypkg import utils\n"
                "        utils.func()\n"
            ),
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        mod_a = _make_module(mod_a_path, imports=[])
        mod_b = _make_module(mod_b_path, imports=[])
        pkg = _make_pkg([mod_a, mod_b])

        result = _find_namespace_modules(pkg)

        assert mod_b_path in result
