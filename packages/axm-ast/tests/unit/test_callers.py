"""Unit tests for forward-reference detection in extract_references.

Covers AC1-AC4 of AXM-1723: extract identifiers from string literals that
appear in typing positions (cast first arg, string annotations, generic
subscript args) while NOT polluting refs from arbitrary strings (logs,
docstrings, regex patterns).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from axm_ast.core.callers import extract_references
from axm_ast.core.dead_code import find_dead_code

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


# ---------------------------------------------------------------------------
# AC1, AC4 — full pipeline: genuinely dead symbols stay dead
# ---------------------------------------------------------------------------


def test_genuinely_dead_symbol_with_no_forward_ref_stays_dead(
    tmp_path: Path,
) -> None:
    """A class with zero references (no calls, no forward refs) is flagged."""
    from axm_ast.core.analyzer import analyze_package

    pkg_root = tmp_path / "sample_pkg"
    src_dir = pkg_root / "src" / "sample"
    src_dir.mkdir(parents=True)
    (pkg_root / "src" / "sample" / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "mod.py").write_text(
        "class TrulyDead:\n    pass\n",
        encoding="utf-8",
    )

    pkg = analyze_package(pkg_root)
    dead = find_dead_code(pkg)
    assert "TrulyDead" in {d.name for d in dead}
