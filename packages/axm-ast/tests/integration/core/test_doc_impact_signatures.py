from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_ast.core.doc_impact import _extract_ast_signatures

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def src_layout(tmp_path: Path) -> Path:
    """Create a project root with a src/ directory."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    return tmp_path


@pytest.fixture()
def flat_layout(tmp_path: Path) -> Path:
    """Create a project root without src/ — .py files at root level."""
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_extract_signatures_functions(src_layout: Path) -> None:
    """Functions are extracted with their first-line signature."""
    py_file = src_layout / "src" / "pkg" / "funcs.py"
    py_file.write_text(
        textwrap.dedent("""\
        def greet(name: str) -> str:
            return f"Hello {name}"

        def add(a: int, b: int) -> int:
            return a + b
        """),
        encoding="utf-8",
    )

    sigs = _extract_ast_signatures(src_layout)

    assert "pkg.funcs.greet" in sigs
    assert sigs["pkg.funcs.greet"] == "def greet(name: str) -> str"
    assert "pkg.funcs.add" in sigs
    assert sigs["pkg.funcs.add"] == "def add(a: int, b: int) -> int"


def test_extract_signatures_classes(src_layout: Path) -> None:
    """Classes are extracted with base classes when present."""
    py_file = src_layout / "src" / "pkg" / "models.py"
    py_file.write_text(
        textwrap.dedent("""\
        class Base:
            pass

        class Child(Base):
            pass

        class Multi(Base, int):
            pass
        """),
        encoding="utf-8",
    )

    sigs = _extract_ast_signatures(src_layout)

    assert sigs["pkg.models.Base"] == "class Base"
    assert sigs["pkg.models.Child"] == "class Child(Base)"
    assert sigs["pkg.models.Multi"] == "class Multi(Base, int)"


def test_extract_signatures_async(src_layout: Path) -> None:
    """Async function defs are correctly extracted."""
    py_file = src_layout / "src" / "pkg" / "async_funcs.py"
    py_file.write_text(
        textwrap.dedent("""\
        async def fetch(url: str) -> bytes:
            return b""

        async def process(data: list[int]) -> None:
            pass
        """),
        encoding="utf-8",
    )

    sigs = _extract_ast_signatures(src_layout)

    assert "pkg.async_funcs.fetch" in sigs
    assert sigs["pkg.async_funcs.fetch"] == "async def fetch(url: str) -> bytes"
    assert "pkg.async_funcs.process" in sigs
    assert (
        sigs["pkg.async_funcs.process"] == "async def process(data: list[int]) -> None"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_syntax_error_skipped(src_layout: Path) -> None:
    """Files with syntax errors are silently skipped."""
    good = src_layout / "src" / "pkg" / "good.py"
    good.write_text("def ok() -> None:\n    pass\n", encoding="utf-8")

    bad = src_layout / "src" / "pkg" / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")

    sigs = _extract_ast_signatures(src_layout)

    assert "pkg.good.ok" in sigs
    # bad.py symbols must not appear, and no exception raised
    assert not any(k.startswith("pkg.bad") for k in sigs)


def test_no_src_directory(flat_layout: Path) -> None:
    """When no src/ exists, .py files at root are found and parsed."""
    py_file = flat_layout / "util.py"
    py_file.write_text("def helper() -> None:\n    pass\n", encoding="utf-8")

    sigs = _extract_ast_signatures(flat_layout)

    assert "util.helper" in sigs
    assert sigs["util.helper"] == "def helper() -> None"


def test_empty_file(src_layout: Path) -> None:
    """A valid .py file with no definitions returns an empty dict contribution."""
    empty = src_layout / "src" / "pkg" / "empty.py"
    empty.write_text("", encoding="utf-8")

    sigs = _extract_ast_signatures(src_layout)

    # __init__.py and empty.py have no defs — no entries from pkg.empty
    assert not any(k.startswith("pkg.empty") for k in sigs)
