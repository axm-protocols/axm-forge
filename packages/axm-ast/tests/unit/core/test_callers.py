"""Unit tests for call-site and reference extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_ast.core.callers import extract_calls, extract_references
from axm_ast.core.parser import extract_module_info


class TestExtractCalls:
    """Test call-site extraction from a single module."""

    def test_simple_function_call(self, tmp_path: Path) -> None:
        """Detects a simple function call."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef setup() -> None:\n    """Set up."""\n    foo()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "foo" in names

    def test_method_call(self, tmp_path: Path) -> None:
        """Detects a method call like self.bar()."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "class X:\n"
            '    """X."""\n'
            "    def run(self) -> None:\n"
            '        """Run."""\n'
            "        self.bar()\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "bar" in names

    def test_chained_call(self, tmp_path: Path) -> None:
        """Detects the last name in a chained call a.b.c()."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef go() -> None:\n    """Go."""\n    a.b.c()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "c" in names

    def test_call_with_args(self, tmp_path: Path) -> None:
        """Call expression text includes arguments."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\ndef go() -> None:\n    """Go."""\n    greet("world", 42)\n'
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        greet_calls = [c for c in calls if c.symbol == "greet"]
        assert len(greet_calls) == 1
        assert "world" in greet_calls[0].call_expression

    def test_nested_calls(self, tmp_path: Path) -> None:
        """Nested calls foo(bar()) produce 2 CallSites."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef go() -> None:\n    """Go."""\n    foo(bar())\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "foo" in names
        assert "bar" in names

    def test_no_calls(self, tmp_path: Path) -> None:
        """Module with no calls returns empty list."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\nx = 42\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls == []

    def test_context_is_enclosing_function(self, tmp_path: Path) -> None:
        """Context field captures enclosing function name."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\ndef main() -> None:\n    """Entry."""\n    setup()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls[0].context == "main"

    def test_context_toplevel(self, tmp_path: Path) -> None:
        """Top-level call has context None."""
        f = tmp_path / "mod.py"
        f.write_text('"""Mod."""\nsetup()\n')
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        assert calls[0].context is None


class TestCallerEdgeCases:
    """Edge cases for caller analysis."""

    def test_call_in_decorator(self, tmp_path: Path) -> None:
        """Call inside a decorator expression is captured."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "@app.route('/foo')\n"
            "def handler() -> None:\n"
            '    """Handle."""\n'
            "    pass\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "route" in names

    def test_call_in_comprehension(self, tmp_path: Path) -> None:
        """Call inside a list comprehension is captured."""
        f = tmp_path / "mod.py"
        f.write_text(
            '"""Mod."""\n'
            "def go() -> None:\n"
            '    """Go."""\n'
            "    xs = [f(x) for x in items]\n"
        )
        mod = extract_module_info(f)
        calls = extract_calls(mod)
        names = [c.symbol for c in calls]
        assert "f" in names


@pytest.fixture()
def mod_factory(tmp_path: Path) -> Callable[[str], SimpleNamespace]:
    """Return a factory that writes source to a temp file.

    Returns a ModuleInfo-like object.
    """

    def _make(source: str) -> SimpleNamespace:
        p = tmp_path / "module.py"
        p.write_text(source, encoding="utf-8")
        return SimpleNamespace(path=p)

    return _make


def test_positional_arg_function_not_dead(mod_factory):
    """A function passed as a positional arg should appear in refs."""
    source = """
def transform():
    pass

map(transform, data)
"""
    refs = extract_references(mod_factory(source))
    assert "transform" in refs


def test_positional_arg_literal_not_ref(mod_factory):
    """Literals and calls in argument_list must NOT produce spurious refs."""
    source = """
def baz():
    pass

foo(42, "str", bar())
"""
    refs = extract_references(mod_factory(source))
    # 42, "str" are literals — not refs
    # bar() is a call — tracked by find_callers, not here
    # baz is defined but never referenced
    assert "baz" not in refs
    assert "bar" not in refs
    assert "42" not in refs


def test_positional_arg_attribute_not_dead(mod_factory):
    """An attribute (obj.method) passed as a positional arg should appear in refs."""
    source = """
register(obj.method)
"""
    refs = extract_references(mod_factory(source))
    assert "method" in refs


def test_star_args_not_ref(mod_factory):
    """foo(*handlers) — star-unpacked name is list_splat, should be skipped."""
    source = """
foo(*handlers)
"""
    refs = extract_references(mod_factory(source))
    assert "handlers" not in refs


def test_multiple_positional_args(mod_factory):
    """Server(host, port, Handler, logger) — only identifiers added as refs."""
    source = """
Server(host, port, Handler, logger)
"""
    refs = extract_references(mod_factory(source))
    assert "Handler" in refs
    assert "logger" in refs
    assert "host" in refs
    assert "port" in refs
