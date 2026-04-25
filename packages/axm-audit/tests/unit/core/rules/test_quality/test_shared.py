"""Unit tests for axm_audit.core.rules.test_quality._shared helpers."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Any

from axm_audit.core.rules.test_quality._shared import (
    analyze_imports,
    collect_pkg_contract_classes,
    collect_pkg_public_symbols,
    current_level_from_path,
    detect_real_io,
    extract_mock_targets,
    fixture_does_io,
    func_attr_io_transitive,
    get_init_all,
    get_module_all,
    get_pkg_prefixes,
    is_import_smoke_test,
    iter_test_files,
    target_matches_io,
)
from axm_audit.core.rules.test_quality._shared import (
    test_is_in_lazy_import_context as is_in_lazy_import_context,
)


def _find_func(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise LookupError(name)


# AC2 ------------------------------------------------------------------


def test_iter_test_files_yields_tests_recursively(tmp_path: Path) -> None:
    unit = tmp_path / "tests" / "unit"
    integ = tmp_path / "tests" / "integration"
    unit.mkdir(parents=True)
    integ.mkdir(parents=True)
    (unit / "test_a.py").write_text("")
    (integ / "test_b.py").write_text("")

    results = list(iter_test_files(tmp_path))
    paths = [r[0] if isinstance(r, tuple) else r for r in results]
    names = [Path(p).name for p in paths]
    assert "test_a.py" in names
    assert "test_b.py" in names
    assert paths == sorted(paths)


# AC3 ------------------------------------------------------------------


def test_get_pkg_prefixes_returns_src_dirs(tmp_path: Path) -> None:
    (tmp_path / "src" / "foo").mkdir(parents=True)
    (tmp_path / "src" / "bar").mkdir(parents=True)
    (tmp_path / "src" / ".hidden").mkdir(parents=True)
    assert get_pkg_prefixes(tmp_path) == {"foo", "bar"}


# AC4 ------------------------------------------------------------------


def test_get_init_all_parses_dunder_all(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text('__all__ = ["X", "Y"]\n')
    result = get_init_all(tmp_path)
    assert result is not None
    assert set(result) == {"X", "Y"}


def test_get_init_all_missing_returns_none(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("x = 1\n")
    assert get_init_all(tmp_path) is None


def test_get_module_all_for_submodule(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "core.py").write_text('__all__ = ["foo", "bar"]\n')
    result = get_module_all(tmp_path, "pkg.core")
    assert result is not None
    assert set(result) == {"foo", "bar"}


# AC5 ------------------------------------------------------------------


def test_current_level_from_path_unit(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "unit" / "x" / "test_a.py"
    assert current_level_from_path(test_file, tests_dir) == "unit"


def test_current_level_from_path_integration_from_functional(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "functional" / "test_x.py"
    assert current_level_from_path(test_file, tests_dir) == "integration"


def test_current_level_from_path_root(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir / "test_root.py"
    assert current_level_from_path(test_file, tests_dir) == "root"


# AC6 ------------------------------------------------------------------


def test_analyze_imports_io_module_names(tmp_path: Path) -> None:
    tree = ast.parse("import httpx as hx\n")
    _public, _internal, _modules, _has_private, io_module_names, io_signals = (
        analyze_imports(tree, set(), None, tmp_path)
    )
    assert "hx" in io_module_names
    assert any("httpx" in s for s in io_signals)


def test_analyze_imports_public_vs_internal(tmp_path: Path) -> None:
    tree = ast.parse("from pkg import Foo, _Bar\n")
    public, internal, _modules, has_private, _io_names, _io_signals = analyze_imports(
        tree, {"pkg"}, {"Foo"}, tmp_path
    )
    assert "Foo" in public
    assert "_Bar" in internal
    assert has_private is True


def test_io_match_shortcircuits_pkg(tmp_path: Path) -> None:
    (tmp_path / "src" / "subprocess").mkdir(parents=True)
    (tmp_path / "src" / "subprocess" / "__init__.py").write_text('__all__ = ["run"]\n')
    tree = ast.parse("from subprocess import run\n")
    public, internal, _modules, _has_private, _io_names, io_signals = analyze_imports(
        tree, {"subprocess"}, {"run"}, tmp_path
    )
    assert io_signals == ["imports subprocess"]
    assert public == []
    assert internal == []


def test_private_name_always_internal(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text('__all__ = ["_helper"]\n')
    (tmp_path / "src" / "pkg" / "mod.py").write_text('__all__ = ["_helper"]\n')
    tree = ast.parse("from pkg.mod import _helper\n")
    public, internal, _modules, has_private, _io_names, _io_signals = analyze_imports(
        tree, {"pkg"}, {"_helper"}, tmp_path
    )
    assert "_helper" in internal
    assert "_helper" not in public
    assert has_private is True


# AC7 ------------------------------------------------------------------


def test_detect_real_io_file_scope_only() -> None:
    code = textwrap.dedent("""
        import subprocess

        def test_x(path):
            subprocess.run(["ls"])
            path.write_text("x")
    """)
    tree = ast.parse(code)
    _has_io, _has_sub, signals = detect_real_io(tree)
    assert any("call:subprocess.run" in s for s in signals)
    assert not any("attr:.write_text" in s for s in signals)


def test_detect_real_io_cli_runner() -> None:
    code = textwrap.dedent("""
        from typer.testing import CliRunner

        def test_cli(app):
            runner = CliRunner()
            runner.invoke(app)
    """)
    tree = ast.parse(code)
    _has_io, has_subprocess, signals = detect_real_io(tree)
    assert has_subprocess is True
    assert any("cli:runner" in s for s in signals)


# AC8 ------------------------------------------------------------------


def test_func_attr_io_transitive_reaches_helper() -> None:
    code = textwrap.dedent("""
        def _helper(p):
            p.write_text("x")

        def test_x(path):
            _helper(path)
    """)
    tree = ast.parse(code)
    helper = _find_func(tree, "_helper")
    test_fn = _find_func(tree, "test_x")
    signals = func_attr_io_transitive(test_fn, {"_helper": helper}, max_depth=2)
    assert any(".write_text" in s for s in signals)


def test_func_attr_io_transitive_depth_limit() -> None:
    code = textwrap.dedent("""
        def level3(p):
            p.write_text("terminal")

        def level2(p):
            level3(p)

        def level1(p):
            level2(p)

        def test_x(path):
            level1(path)
    """)
    tree = ast.parse(code)
    helpers = {
        "level1": _find_func(tree, "level1"),
        "level2": _find_func(tree, "level2"),
        "level3": _find_func(tree, "level3"),
    }
    test_fn = _find_func(tree, "test_x")
    signals = func_attr_io_transitive(test_fn, helpers, max_depth=2)
    assert not any("write_text" in s for s in signals)


# AC9 ------------------------------------------------------------------


def test_fixture_does_io_direct_attr() -> None:
    code = textwrap.dedent("""
        import pytest

        @pytest.fixture
        def foo():
            target.mkdir()
    """)
    tree = ast.parse(code)
    fixtures = {"foo": _find_func(tree, "foo")}
    assert fixture_does_io("foo", fixtures, set(), 0) is True


def test_fixture_does_io_transitive_tmp_path() -> None:
    code = textwrap.dedent("""
        import pytest

        @pytest.fixture
        def bar(tmp_path):
            p = tmp_path / "x"
            return p
    """)
    tree = ast.parse(code)
    fixtures = {"bar": _find_func(tree, "bar")}
    assert fixture_does_io("bar", fixtures, set(), 0) is True


def test_fixture_does_io_depth_guard() -> None:
    code = textwrap.dedent("""
        import pytest

        @pytest.fixture
        def d(tmp_path):
            tmp_path.mkdir()

        @pytest.fixture
        def c(d):
            return d

        @pytest.fixture
        def b(c):
            return c

        @pytest.fixture
        def a(b):
            return b
    """)
    tree = ast.parse(code)
    fixtures = {
        "a": _find_func(tree, "a"),
        "b": _find_func(tree, "b"),
        "c": _find_func(tree, "c"),
        "d": _find_func(tree, "d"),
    }
    assert fixture_does_io("a", fixtures, set(), 0) is False


def test_fixture_does_io_conftest_cache(tmp_path: Path, mocker: Any) -> None:
    conftest = tmp_path / "conftest.py"
    conftest.write_text(
        textwrap.dedent("""
        import pytest

        @pytest.fixture
        def bar(tmp_path):
            tmp_path.mkdir()
            return tmp_path
    """)
    )

    from axm_audit.core.rules.test_quality import _shared

    _shared._CONFTEST_CACHE.clear()

    first = _shared._load_conftest_fixtures(conftest)
    assert "bar" in first

    mocker.patch.object(
        Path, "read_text", side_effect=AssertionError("cache should be hit")
    )
    second = _shared._load_conftest_fixtures(conftest)
    assert "bar" in second


# AC10 -----------------------------------------------------------------


def test_collect_pkg_public_symbols_functions_classes_vars(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "mod.py").write_text(
        textwrap.dedent("""
        def f():
            pass

        class C:
            pass

        X = 1
    """)
    )
    symbols = collect_pkg_public_symbols(tmp_path)
    assert {"f", "C", "X"}.issubset(set(symbols))


# AC11 -----------------------------------------------------------------


def test_collect_contract_classes_local_protocol(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "p.py").write_text(
        textwrap.dedent("""
        from typing import Protocol

        class Foo(Protocol):
            def run(self): ...
    """)
    )
    classes = collect_pkg_contract_classes(tmp_path)
    assert "Foo" in classes


def test_collect_contract_classes_sibling_package(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    pkg1 = packages / "pkg1"
    pkg2 = packages / "pkg2"
    (pkg1 / "src" / "pkg1").mkdir(parents=True)
    (pkg1 / "src" / "pkg1" / "__init__.py").write_text("")
    (pkg2 / "src" / "pkg2").mkdir(parents=True)
    (pkg2 / "src" / "pkg2" / "__init__.py").write_text("")
    (pkg2 / "src" / "pkg2" / "contracts.py").write_text(
        textwrap.dedent("""
        from abc import ABC

        class Bar(ABC):
            pass
    """)
    )
    classes = collect_pkg_contract_classes(pkg1)
    assert "Bar" in classes


def test_collect_contract_classes_runtime_checkable_decorator(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "p.py").write_text(
        textwrap.dedent("""
        from typing import Protocol, runtime_checkable

        @runtime_checkable
        class Baz(Protocol):
            def run(self): ...
    """)
    )
    classes = collect_pkg_contract_classes(tmp_path)
    assert "Baz" in classes


# AC12 -----------------------------------------------------------------


def test_is_import_smoke_test_positive() -> None:
    code = textwrap.dedent('''
        def test_x():
            """doc"""
            from x import Y
            assert Y is not None
    ''')
    func = _find_func(ast.parse(code), "test_x")
    assert is_import_smoke_test(func) is True


def test_is_import_smoke_test_rejects_5_stmts() -> None:
    code = textwrap.dedent("""
        def test_x():
            a = 1
            b = 2
            c = 3
            d = 4
            e = 5
    """)
    func = _find_func(ast.parse(code), "test_x")
    assert is_import_smoke_test(func) is False


# AC13 -----------------------------------------------------------------


def test_lazy_import_context_filename(tmp_path: Path) -> None:
    test_file = tmp_path / "test_init.py"
    code = "def test_x(): pass\n"
    test_file.write_text(code)
    tree = ast.parse(code)
    func = _find_func(tree, "test_x")
    assert is_in_lazy_import_context(func, tree, test_file) is True


def test_lazy_import_context_docstring_getattr(tmp_path: Path) -> None:
    test_file = tmp_path / "test_thing.py"
    code = textwrap.dedent('''
        """This module tests __getattr__ lazy import behavior."""

        def test_x(): pass
    ''')
    test_file.write_text(code)
    tree = ast.parse(code)
    func = _find_func(tree, "test_x")
    assert is_in_lazy_import_context(func, tree, test_file) is True


# AC14 -----------------------------------------------------------------


def test_extract_mock_targets_patch_string() -> None:
    code = textwrap.dedent("""
        def test_x():
            with patch("pkg.mod.run"):
                pass
    """)
    func = _find_func(ast.parse(code), "test_x")
    targets = extract_mock_targets(func)
    assert "pkg.mod.run" in targets


def test_extract_mock_targets_patch_object() -> None:
    code = textwrap.dedent("""
        def test_x():
            with patch.object(obj, "attr"):
                pass
    """)
    func = _find_func(ast.parse(code), "test_x")
    targets = extract_mock_targets(func)
    assert "obj.attr" in targets


def test_extract_mock_targets_monkeypatch_setattr_2_args() -> None:
    code = textwrap.dedent("""
        def test_x(monkeypatch):
            monkeypatch.setattr("pkg.mod.run", X)
    """)
    func = _find_func(ast.parse(code), "test_x")
    targets = extract_mock_targets(func)
    assert "pkg.mod.run" in targets


def test_extract_mock_targets_mock_factories() -> None:
    code = textwrap.dedent("""
        def test_x():
            m = MagicMock()
    """)
    func = _find_func(ast.parse(code), "test_x")
    targets = extract_mock_targets(func)
    assert "mock-factory:MagicMock" in targets


# AC15 -----------------------------------------------------------------


def test_target_matches_io_direct_call() -> None:
    assert target_matches_io("subprocess.run") is True


def test_target_matches_io_dotted_suffix() -> None:
    assert target_matches_io("pkg.inner.subprocess.run") is True


def test_target_matches_io_module_leaf_token() -> None:
    assert target_matches_io("pkg.mod.httpx") is True


def test_target_matches_io_non_match() -> None:
    assert target_matches_io("pkg.mod.helper") is False
