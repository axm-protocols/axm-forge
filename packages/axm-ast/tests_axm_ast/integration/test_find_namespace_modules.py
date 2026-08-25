"""Split from ``test_dead_code.py``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_ns_module(path: Path, *, imports: list[object] | None = None) -> MagicMock:
    """Create a minimal ModuleInfo-like mock."""
    mod = MagicMock()
    mod.path = path
    mod.imports = imports or []
    return mod


def _make_ns_import(
    *, module: str | None = None, names: list[str] | None = None
) -> MagicMock:
    """Create a minimal ImportInfo-like mock."""
    imp = MagicMock()
    imp.module = module
    imp.names = names or []
    return imp


def _make_ns_pkg(modules: list[object]) -> MagicMock:
    """Create a minimal PackageInfo-like mock."""
    pkg = MagicMock()
    pkg.modules = modules
    return pkg


def _write_source(path: Path, source: str) -> Path:
    """Write a Python source file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


class TestLazyImportNamespaceDetectionIntegration:
    """Lazy `from pkg import mod` inside function bodies detects namespace modules."""

    @pytest.mark.parametrize(
        ("caller_source", "utils_source"),
        [
            pytest.param(
                "def do_work():\n    from mypkg import utils\n    utils.func()\n",
                "def func():\n    return 42\n",
                id="basic_lazy_import",
            ),
            pytest.param(
                "def do_work():\n    from mypkg import utils\n    utils.func()\n",
                "def _helper():\n    return 1\n\ndef func():\n    return _helper()\n",
                id="utils_has_private_helper",
            ),
            pytest.param(
                "def work():\n    from mypkg import utils as u\n    u.func()\n",
                "def func():\n    return 1\n",
                id="lazy_import_with_alias",
            ),
            pytest.param(
                (
                    "def outer():\n"
                    "    def inner():\n"
                    "        from mypkg import utils\n"
                    "        utils.func()\n"
                ),
                "def func():\n    return 1\n",
                id="lazy_import_in_nested_function",
            ),
        ],
    )
    def test_lazy_import_variants_detect_namespace(
        self, tmp_path: Path, caller_source: str, utils_source: str
    ) -> None:
        from axm_ast.core.dead_code import find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(pkg_dir / "caller.py", caller_source)
        mod_b_path = _write_source(pkg_dir / "utils.py", utils_source)

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_lazy_symbol_import_not_namespace(self, tmp_path: Path) -> None:
        """from pkg.mod import func (symbol, not module) → mod NOT namespace."""
        from axm_ast.core.dead_code import find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "def do_work():\n    from mypkg.utils import func\n    func()\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 42\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = find_namespace_modules(pkg)

        assert mod_b_path not in result

    def test_both_module_level_and_lazy(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import find_namespace_modules

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

        imp_a = _make_ns_import(module="mypkg", names=["helpers"])
        mod_a = _make_ns_module(mod_a_path, imports=[imp_a])
        mod_c = _make_ns_module(mod_c_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_c, mod_b])

        result = find_namespace_modules(pkg)

        assert mod_b_path in result

    def test_no_imports_returns_empty_set(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "alpha.py",
            "def foo():\n    return 1\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "beta.py",
            "x = 42\n",
        )

        mod_a = _make_ns_module(mod_a_path, imports=[])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = find_namespace_modules(pkg)

        assert result == set()

    def test_mixed_bare_and_from_imports_single_entry(self, tmp_path: Path) -> None:
        from axm_ast.core.dead_code import find_namespace_modules

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        mod_a_path = _write_source(
            pkg_dir / "caller.py",
            "import mypkg.utils\nfrom mypkg import utils\n",
        )
        mod_b_path = _write_source(
            pkg_dir / "utils.py",
            "def func():\n    return 1\n",
        )

        imp_bare = _make_ns_import(module="mypkg.utils", names=[])
        imp_from = _make_ns_import(module="mypkg", names=["utils"])
        mod_a = _make_ns_module(mod_a_path, imports=[imp_bare, imp_from])
        mod_b = _make_ns_module(mod_b_path, imports=[])
        pkg = _make_ns_pkg([mod_a, mod_b])

        result = find_namespace_modules(pkg)

        assert mod_b_path in result
        assert len(result) == 1
