"""Unit tests for forward-reference detection in extract_references.

Covers AC1-AC4 of AXM-1723: extract identifiers from string literals that
appear in typing positions (cast first arg, string annotations, generic
subscript args) while NOT polluting refs from arbitrary strings (logs,
docstrings, regex patterns).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from axm_ast.core.callers import extract_references

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture()
def mod_factory(tmp_path: Path) -> Callable[[str], SimpleNamespace]:
    """Return a factory that writes source to a temp file.

    Returns a ModuleInfo-like object (only ``.path`` is read by
    ``extract_references``).
    """

    def _make(source: str) -> SimpleNamespace:
        p = tmp_path / "module.py"
        p.write_text(source, encoding="utf-8")
        return SimpleNamespace(path=p)

    return _make


# ---------------------------------------------------------------------------
# AC1 — cast("Foo", value) and cast(Foo, value)
# ---------------------------------------------------------------------------


def test_cast_string_first_arg_collects_typename(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
from typing import cast

data = object()
typed = cast("Foo", data)
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


def test_cast_non_string_first_arg_collects_nothing_extra(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
from typing import cast

class Foo:
    pass

data = object()
typed = cast(Foo, data)
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


# ---------------------------------------------------------------------------
# AC2 — string annotations on variable / return / parameter
# ---------------------------------------------------------------------------


def test_string_variable_annotation_collected(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
def make():
    return object()

x: "Foo" = make()
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


def test_string_return_annotation_collected(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
def f() -> "Foo":
    ...
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


def test_string_parameter_annotation_collected(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
def f(x: "Foo") -> None:
    ...
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


# ---------------------------------------------------------------------------
# AC3 — generic-subscript string args
# ---------------------------------------------------------------------------


def test_subscript_string_arg_collected(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
x: list["Foo"] = []
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs


def test_nested_typing_string_collected(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
from typing import Annotated

x: Annotated["Foo", "meta"] = object()
"""
    refs = extract_references(mod_factory(source))
    assert "Foo" in refs
    assert "meta" not in refs


def test_multiple_identifiers_in_one_string(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
x: "dict[str, MyClass]" = {}
"""
    refs = extract_references(mod_factory(source))
    assert {"dict", "str", "MyClass"} <= refs


# ---------------------------------------------------------------------------
# AC4 — negative: arbitrary strings outside typing positions
# ---------------------------------------------------------------------------


def test_log_string_does_not_pollute_refs(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = """
import logging

logger = logging.getLogger(__name__)
logger.info("MyClass failed to load")
"""
    refs = extract_references(mod_factory(source))
    assert "MyClass" not in refs


def test_docstring_does_not_pollute_refs(
    mod_factory: Callable[[str], SimpleNamespace],
) -> None:
    source = '''
def f():
    """Uses MyClass internally."""
    return 1
'''
    refs = extract_references(mod_factory(source))
    assert "MyClass" not in refs


@pytest.fixture()
def mod_factory__from_core_callers(tmp_path: Path) -> Callable[[str], SimpleNamespace]:
    """Return a factory that writes source to a temp file.

    Returns a ModuleInfo-like object.
    """

    def _make(source: str) -> SimpleNamespace:
        p = tmp_path / "module.py"
        p.write_text(source, encoding="utf-8")
        return SimpleNamespace(path=p)

    return _make


def test_positional_arg_function_not_dead(mod_factory__from_core_callers):
    """A function passed as a positional arg should appear in refs."""
    source = """
def transform():
    pass

map(transform, data)
"""
    refs = extract_references(mod_factory__from_core_callers(source))
    assert "transform" in refs


def test_positional_arg_literal_not_ref(mod_factory__from_core_callers):
    """Literals and calls in argument_list must NOT produce spurious refs."""
    source = """
def baz():
    pass

foo(42, "str", bar())
"""
    refs = extract_references(mod_factory__from_core_callers(source))
    # 42, "str" are literals — not refs
    # bar() is a call — tracked by find_callers, not here
    # baz is defined but never referenced
    assert "baz" not in refs
    assert "bar" not in refs
    assert "42" not in refs


def test_positional_arg_attribute_not_dead(mod_factory__from_core_callers):
    """An attribute (obj.method) passed as a positional arg should appear in refs."""
    source = """
register(obj.method)
"""
    refs = extract_references(mod_factory__from_core_callers(source))
    assert "method" in refs


def test_star_args_not_ref(mod_factory__from_core_callers):
    """foo(*handlers) — star-unpacked name is list_splat, should be skipped."""
    source = """
foo(*handlers)
"""
    refs = extract_references(mod_factory__from_core_callers(source))
    assert "handlers" not in refs


def test_multiple_positional_args(mod_factory__from_core_callers):
    """Server(host, port, Handler, logger) — only identifiers added as refs."""
    source = """
Server(host, port, Handler, logger)
"""
    refs = extract_references(mod_factory__from_core_callers(source))
    assert "Handler" in refs
    assert "logger" in refs
    assert "host" in refs
    assert "port" in refs
