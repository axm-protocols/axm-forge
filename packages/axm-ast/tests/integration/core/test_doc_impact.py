from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.doc_impact import _extract_ast_signatures, find_stale_signatures

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def src_tree(tmp_path: Path) -> Path:
    """Return *tmp_path* with a ``src/pkg/`` directory pre-created."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    return tmp_path


def _write_module(root: Path, code: str, module: str = "pkg.mod") -> Path:
    parts = module.split(".")
    directory = root / "src" / Path(*parts[:-1])
    directory.mkdir(parents=True, exist_ok=True)
    py_file = directory / f"{parts[-1]}.py"
    py_file.write_text(code, encoding="utf-8")
    return py_file


# ---------------------------------------------------------------------------
# Unit tests — ClassDef signature extraction
# ---------------------------------------------------------------------------


def test_classdef_with_bases(src_tree: Path) -> None:
    _write_module(src_tree, "class Foo(Bar, Baz): pass\n")
    sigs = _extract_ast_signatures(src_tree)
    assert sigs["pkg.mod.Foo"] == "class Foo(Bar, Baz)"


def test_classdef_no_bases(src_tree: Path) -> None:
    _write_module(src_tree, "class Foo: pass\n")
    sigs = _extract_ast_signatures(src_tree)
    assert sigs["pkg.mod.Foo"] == "class Foo"


def test_classdef_dotted_base(src_tree: Path) -> None:
    _write_module(src_tree, "class Foo(mod.Base): pass\n")
    sigs = _extract_ast_signatures(src_tree)
    assert sigs["pkg.mod.Foo"] == "class Foo(mod.Base)"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_classdef_generic_base(src_tree: Path) -> None:
    _write_module(src_tree, "class Foo(list[int]): pass\n")
    sigs = _extract_ast_signatures(src_tree)
    assert sigs["pkg.mod.Foo"] == "class Foo(list[int])"


# ---------------------------------------------------------------------------
# Functional — stale base-class detection
# ---------------------------------------------------------------------------


def test_stale_base_class_change(src_tree: Path) -> None:
    """Doc says ``class Foo(OldBase)`` but code says ``class Foo(NewBase)``."""
    _write_module(src_tree, "class Foo(NewBase): pass\n")

    # Create a markdown doc referencing the old base class
    docs_dir = src_tree / "docs"
    docs_dir.mkdir()
    doc_file = docs_dir / "pkg.mod.md"
    doc_file.write_text(
        "# pkg.mod\n\n## Classes\n\n### Foo\n\n```python\nclass Foo(OldBase)\n```\n",
        encoding="utf-8",
    )

    stale = find_stale_signatures(src_tree)
    # At least one stale entry for Foo with both old and new signatures
    foo_entries = [s for s in stale if "Foo" in str(s)]
    assert foo_entries, "Expected stale entry for Foo with changed base class"
    stale_str = str(foo_entries)
    assert "OldBase" in stale_str
    assert "NewBase" in stale_str
