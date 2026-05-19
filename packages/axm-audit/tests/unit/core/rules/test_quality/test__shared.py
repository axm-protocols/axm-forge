"""Unit tests for axm_audit.core.rules.test_quality._shared helpers."""

from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.test_quality._shared import (
    detect_real_io,
    extract_mock_targets,
    fixture_does_io,
    func_attr_io_transitive,
    has_in_package_subprocess_invocation,
    is_import_smoke_test,
    target_matches_io,
)


def _find_func(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise LookupError(name)


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


def test_subprocess_sets_has_subprocess() -> None:
    code = textwrap.dedent("""
        import subprocess

        def test_run():
            subprocess.run(["ls"])
    """)
    tree = ast.parse(code)
    has_io, has_subprocess, signals = detect_real_io(tree)
    assert has_io is True
    assert has_subprocess is True
    assert "call:subprocess.run" in signals


def test_cli_runner_sets_has_subprocess() -> None:
    code = textwrap.dedent("""
        from typer.testing import CliRunner

        def test_cli(app):
            CliRunner().invoke(app, ["--help"])
    """)
    tree = ast.parse(code)
    has_io, has_subprocess, signals = detect_real_io(tree)
    assert has_io is True
    assert has_subprocess is True
    assert "cli:CliRunner" in signals


def test_no_io_returns_empty() -> None:
    code = textwrap.dedent("""
        def test_pure():
            assert 1 + 1 == 2
    """)
    tree = ast.parse(code)
    assert detect_real_io(tree) == (False, False, [])


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


@pytest.mark.parametrize(
    ("code", "entry", "fixture_names", "expected"),
    [
        pytest.param(
            """
        import pytest

        @pytest.fixture
        def foo():
            target.mkdir()
    """,
            "foo",
            ("foo",),
            True,
            id="direct_attr",
        ),
        pytest.param(
            """
        import pytest

        @pytest.fixture
        def bar(tmp_path):
            p = tmp_path / "x"
            return p
    """,
            "bar",
            ("bar",),
            True,
            id="transitive_tmp_path",
        ),
        pytest.param(
            """
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
    """,
            "a",
            ("a", "b", "c", "d"),
            False,
            id="depth_guard",
        ),
    ],
)
def test_fixture_does_io(
    code: str,
    entry: str,
    fixture_names: tuple[str, ...],
    expected: bool,
) -> None:
    tree = ast.parse(textwrap.dedent(code))
    fixtures = {name: _find_func(tree, name) for name in fixture_names}
    assert fixture_does_io(entry, fixtures, set(), 0) is expected


# AC12 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            '''
        def test_x():
            """doc"""
            from x import Y
            assert Y is not None
    ''',
            True,
            id="positive_is_not_none",
        ),
        pytest.param(
            """
        def test_x():
            a = 1
            b = 2
            c = 3
            d = 4
            e = 5
    """,
            False,
            id="rejects_5_stmts",
        ),
        pytest.param(
            """
        def test_x():
            from x import Y
            assert isinstance(Y, int)
    """,
            True,
            id="isinstance_assert",
        ),
        pytest.param(
            """
        def test_x():
            from x import Y
            assert Y
    """,
            True,
            id="bare_name_assert",
        ),
        pytest.param(
            """
        def test_x(self):
            from x import Y
            self.assertIsNotNone(Y)
    """,
            True,
            id="self_assert_is_not_none",
        ),
        pytest.param(
            """
        def test_x():
            from x import Y
            assert Y == 42
    """,
            False,
            id="strong_assert",
        ),
        pytest.param(
            """
        def test_x():
            assert Y is not None
    """,
            False,
            id="no_import",
        ),
        pytest.param(
            """
        def test_x():
            from x import Y
            assert Y is not None
            a = 1
            b = 2
            c = 3
    """,
            False,
            id="body_over_budget",
        ),
    ],
)
def test_is_import_smoke_test(code: str, expected: bool) -> None:
    func = _find_func(ast.parse(textwrap.dedent(code)), "test_x")
    assert is_import_smoke_test(func) is expected


# AC14 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_target"),
    [
        pytest.param(
            """
        def test_x():
            with patch("pkg.mod.run"):
                pass
    """,
            "pkg.mod.run",
            id="patch_string",
        ),
        pytest.param(
            """
        def test_x():
            with patch.object(obj, "attr"):
                pass
    """,
            "obj.attr",
            id="patch_object",
        ),
        pytest.param(
            """
        def test_x(monkeypatch):
            monkeypatch.setattr("pkg.mod.run", X)
    """,
            "pkg.mod.run",
            id="monkeypatch_setattr_2_args",
        ),
        pytest.param(
            """
        def test_x():
            m = MagicMock()
    """,
            "mock-factory:MagicMock",
            id="mock_factories",
        ),
    ],
)
def test_extract_mock_targets(code: str, expected_target: str) -> None:
    func = _find_func(ast.parse(textwrap.dedent(code)), "test_x")
    targets = extract_mock_targets(func)
    assert expected_target in targets


# AC15 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param("subprocess.run", True, id="direct_call"),
        pytest.param("pkg.inner.subprocess.run", True, id="dotted_suffix"),
        pytest.param("pkg.mod.httpx", True, id="module_leaf_token"),
        pytest.param("pkg.mod.helper", False, id="non_match"),
    ],
)
def test_target_matches_io(target: str, expected: bool) -> None:
    """target_matches_io detects I/O targets via dotted suffix or leaf token."""
    assert target_matches_io(target) is expected


# AC1 — helpers moved from pyramid_level to _shared
# ---------------------------------------------------------------------


def test_has_in_package_subprocess_invocation_via_shared() -> None:
    """AC1: helper returns True for in-package, False for plumbing."""
    in_pkg = ast.parse(
        textwrap.dedent(
            """
            import subprocess
            subprocess.run(["pkg-cli", "do"], check=True)
            """
        ).strip()
    )
    plumbing = ast.parse(
        textwrap.dedent(
            """
            import subprocess
            subprocess.run(["git", "init"], check=True)
            """
        ).strip()
    )
    in_pkg_call = next(n for n in ast.walk(in_pkg) if isinstance(n, ast.Call))
    plumb_call = next(n for n in ast.walk(plumbing) if isinstance(n, ast.Call))

    assert has_in_package_subprocess_invocation(
        call=in_pkg_call,
        module_ast=in_pkg,
        project_scripts={"pkg-cli"},
    )
    assert not has_in_package_subprocess_invocation(
        call=plumb_call,
        module_ast=plumbing,
        project_scripts={"pkg-cli"},
    )
