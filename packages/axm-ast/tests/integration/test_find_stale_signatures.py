"""Stale signature detection — drives ``find_stale_signatures`` (public seam).

Merges the former ``test_extract_ast_signatures.py`` and
``test_extract_doc_signatures.py`` edge-case suites: both private helpers
(:func:`_extract_ast_signatures`, :func:`_extract_doc_signatures`) are exercised
transitively via :func:`find_stale_signatures`, which compares AST signatures
against doc-code-block signatures and emits :class:`StaleSignature` records.

Each AST/doc edge case is observed by setting up a source module with a known
signature plus a doc file with either a matching or drifted signature, then
asserting on the resulting stale list (``doc_sig`` reflects the doc extractor,
``actual_sig`` reflects the AST extractor).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.doc_impact import StaleSignature, find_stale_signatures
from tests.integration._helpers import _write_module


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


def _make_pkg(
    tmp_path: Path,
    *,
    src_code: str,
    readme: str | None = None,
    docs: dict[str, str] | None = None,
) -> Path:
    """Create a minimal Python package with optional docs.

    Returns the project root (tmp_path), not the src dir.
    """
    # Source package
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""mypkg."""\n')
    (pkg / "core.py").write_text(src_code)

    # pyproject.toml (needed for analyze_package)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )

    # README
    if readme is not None:
        (tmp_path / "README.md").write_text(readme)

    # docs/
    if docs is not None:
        for name, content in docs.items():
            doc_path = tmp_path / "docs" / name
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content)

    return tmp_path


class TestFindStaleSignatures:
    """Test detection of stale code signatures in docs."""

    def test_stale_signature_detected(self, tmp_path: Path) -> None:
        """Code block with `def foo(a)`, real AST `def foo(a, b)` → stale."""
        root = _make_pkg(
            tmp_path,
            src_code=(
                "def foo(a: int, b: int) -> int:\n"
                '    """Add two numbers."""\n'
                "    return a + b\n"
            ),
            readme=("# Project\n\n```python\ndef foo(a):\n    ...\n```\n"),
        )
        stale = find_stale_signatures(root, ["foo"])
        assert len(stale) > 0
        assert any(s["symbol"] == "foo" for s in stale)

    def test_stale_signature_has_line(self, tmp_path: Path) -> None:
        """Stale entry includes line number from the doc file."""
        root = _make_pkg(
            tmp_path,
            src_code=(
                'def foo(a: int, b: int) -> int:\n    """Add."""\n    return a + b\n'
            ),
            readme=("# Project\n\n\n```python\ndef foo(a):\n    ...\n```\n"),
        )
        stale = find_stale_signatures(root, ["foo"])
        assert len(stale) == 1
        assert stale[0]["symbol"] == "foo"
        assert stale[0]["line"] == 5

    def test_stale_signature_clean(self, tmp_path: Path) -> None:
        """Code block matches AST signature → stale_signatures empty."""
        root = _make_pkg(
            tmp_path,
            src_code=(
                "def foo(a: int, b: int) -> int:\n"
                '    """Add two numbers."""\n'
                "    return a + b\n"
            ),
            readme=(
                "# Project\n\n"
                "```python\n"
                "def foo(a: int, b: int) -> int:\n"
                "    ...\n"
                "```\n"
            ),
        )
        stale = find_stale_signatures(root, ["foo"])
        assert len(stale) == 0


def _write_doc_with_sig(doc_path: Path, symbol: str, sig_line: str) -> None:
    """Write a minimal markdown doc containing a code block with a signature."""
    doc_path.write_text(f"# Reference\n\n```python\n{sig_line}:\n    pass\n```\n")


def test_find_stale_no_collision(tmp_path: Path) -> None:
    """Stale signature detected when doc differs from AST (no collision)."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text("def foo(x: int):\n    pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc_with_sig(docs / "ref.md", "foo", "def foo(x: str)")

    stale = find_stale_signatures(tmp_path, ["foo"])

    assert len(stale) >= 1
    assert any(e["symbol"] == "foo" for e in stale)


def test_find_stale_with_collision(tmp_path: Path) -> None:
    """Two modules with same-named function; doc references one — no false positive."""
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir(parents=True)
    (src / "a" / "__init__.py").write_text("")
    (src / "b" / "__init__.py").write_text("")
    (src / "a" / "foo.py").write_text("def parse(x: int):\n    return x\n")
    (src / "b" / "foo.py").write_text("def parse(y: str):\n    return y\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    # Doc matches a.foo.parse exactly — should NOT be stale
    _write_doc_with_sig(docs / "ref.md", "parse", "def parse(x: int)")

    stale = find_stale_signatures(tmp_path, ["parse"])

    # Should not report as stale since at least one actual signature matches
    # OR if conservative: reports stale only when ALL qualified matches differ
    # The key point: no crash, correct match logic
    assert not any(
        e["symbol"] == "parse"
        and e.get("actual_sig", "").strip() == "def parse(x: int)"
        for e in stale
    )


def test_symbol_not_in_ast_no_crash(tmp_path: Path) -> None:
    """Doc references a removed function — no crash, not in stale list."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text("def other():\n    pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    _write_doc_with_sig(docs / "ref.md", "removed_func", "def removed_func()")

    stale = find_stale_signatures(tmp_path, ["removed_func"])

    # Symbol not in AST → cannot compare → not reported as stale
    assert not any(e["symbol"] == "removed_func" for e in stale)


# ---------------------------------------------------------------------------
# Fixtures for AST / doc extractor edge cases
# ---------------------------------------------------------------------------


@pytest.fixture()
def src_layout(tmp_path: Path) -> Path:
    """Project root with ``src/pkg/`` directory pre-created."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    return tmp_path


@pytest.fixture()
def flat_layout(tmp_path: Path) -> Path:
    """Project root without ``src/`` — ``.py`` files at root level."""
    return tmp_path


def _write_doc(root: Path, name: str, content: str) -> Path:
    """Write a doc file under ``root/docs/`` (creating the directory)."""
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    p = docs / name
    p.write_text(content, encoding="utf-8")
    return p


def _stale_for(stale: list[StaleSignature], symbol: str) -> list[StaleSignature]:
    return [s for s in stale if s["symbol"] == symbol]


# ---------------------------------------------------------------------------
# AST extractor edge cases (formerly tests/integration/test_extract_ast_signatures.py)
#
# Driven via ``find_stale_signatures``: the AST-extracted signature surfaces in
# the ``actual_sig`` field of each ``StaleSignature`` record when the doc-side
# signature drifts.
# ---------------------------------------------------------------------------


class TestFindStaleSignaturesAstExtraction:
    """AST-side edge cases — exercises the AST signature extraction path."""

    def test_extracts_function_signature(self, src_layout: Path) -> None:
        """Function signatures are extracted with full type annotations."""
        (src_layout / "src" / "pkg" / "funcs.py").write_text(
            "def greet(name: str) -> str:\n    return name\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\ndef greet(other: int) -> int:\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["greet"])

        assert len(stale) == 1
        assert stale[0]["actual_sig"] == "def greet(name: str) -> str"

    def test_extracts_multiple_functions(self, src_layout: Path) -> None:
        """Two functions in one module both surface their AST signatures."""
        (src_layout / "src" / "pkg" / "funcs.py").write_text(
            "def greet(name: str) -> str:\n    return name\n\n"
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\ndef greet(x):\n    pass\ndef add(x):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["greet", "add"])

        actual_sigs = {s["actual_sig"] for s in stale}
        assert "def greet(name: str) -> str" in actual_sigs
        assert "def add(a: int, b: int) -> int" in actual_sigs

    def test_extracts_class_no_bases(self, src_layout: Path) -> None:
        """Bare class definitions extract as ``class Name``."""
        (src_layout / "src" / "pkg" / "models.py").write_text(
            "class Base:\n    pass\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\nclass Base(SomeOther):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["Base"])

        assert len(stale) == 1
        assert stale[0]["actual_sig"] == "class Base"

    def test_extracts_class_with_single_base(self, src_layout: Path) -> None:
        """Class with one base extracts as ``class Name(Base)``."""
        (src_layout / "src" / "pkg" / "models.py").write_text(
            "class Base: pass\nclass Child(Base): pass\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\nclass Child(OtherBase):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["Child"])

        assert any(s["actual_sig"] == "class Child(Base)" for s in stale)

    def test_extracts_class_with_multiple_bases(self, src_layout: Path) -> None:
        """Multi-inheritance is rendered as ``class Name(B1, B2)``."""
        (src_layout / "src" / "pkg" / "models.py").write_text(
            "class Base: pass\nclass Multi(Base, int): pass\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\nclass Multi(OnlyOne):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["Multi"])

        assert any(s["actual_sig"] == "class Multi(Base, int)" for s in stale)

    def test_extracts_classdef_with_dotted_base(self, src_tree: Path) -> None:
        """Dotted base classes are rendered verbatim (``mod.Base``)."""
        _write_module(src_tree, "class Foo(mod.Base): pass\n")
        _write_doc(
            src_tree,
            "api.md",
            "```python\nclass Foo(WrongBase):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_tree, ["Foo"])

        assert any(s["actual_sig"] == "class Foo(mod.Base)" for s in stale)

    def test_extracts_classdef_with_generic_base(self, src_tree: Path) -> None:
        """Generic bases like ``list[int]`` are preserved in the signature."""
        _write_module(src_tree, "class Foo(list[int]): pass\n")
        _write_doc(
            src_tree,
            "api.md",
            "```python\nclass Foo(list):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_tree, ["Foo"])

        assert any(s["actual_sig"] == "class Foo(list[int])" for s in stale)

    def test_extracts_async_function(self, src_layout: Path) -> None:
        """Async def is preserved as the leading token in the AST signature.

        The doc extractor's ``_DEF_RE`` only matches ``def``/``class`` tokens,
        so we drift via a sync ``def fetch`` in the doc against the async
        AST signature — the resulting ``actual_sig`` proves the AST extractor
        retained the ``async`` prefix.
        """
        (src_layout / "src" / "pkg" / "async_funcs.py").write_text(
            "async def fetch(url: str) -> bytes:\n    return b''\n",
            encoding="utf-8",
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\ndef fetch(url: str) -> bytes:\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_layout, ["fetch"])

        assert len(stale) == 1
        assert stale[0]["actual_sig"] == "async def fetch(url: str) -> bytes"

    def test_skips_syntax_error_files(self, src_layout: Path) -> None:
        """A file with a syntax error is silently skipped — other files succeed."""
        good = src_layout / "src" / "pkg" / "good.py"
        good.write_text("def ok(x: int) -> None:\n    pass\n", encoding="utf-8")
        bad = src_layout / "src" / "pkg" / "bad.py"
        bad.write_text("def broken(:\n", encoding="utf-8")

        _write_doc(
            src_layout,
            "api.md",
            "```python\ndef ok(x):\n    pass\n```\n",
        )

        # Must not raise despite bad.py — and must still detect drift in good.py.
        stale = find_stale_signatures(src_layout, ["ok"])

        assert any(s["actual_sig"] == "def ok(x: int) -> None" for s in stale)

    def test_flat_layout_without_src_directory(self, flat_layout: Path) -> None:
        """Without ``src/``, ``.py`` files at root are still scanned."""
        (flat_layout / "util.py").write_text(
            "def helper() -> None:\n    pass\n", encoding="utf-8"
        )
        _write_doc(
            flat_layout,
            "api.md",
            "```python\ndef helper(x: int) -> int:\n    pass\n```\n",
        )

        stale = find_stale_signatures(flat_layout, ["helper"])

        assert len(stale) == 1
        assert stale[0]["actual_sig"] == "def helper() -> None"

    def test_empty_file_contributes_nothing(self, src_layout: Path) -> None:
        """A valid but empty ``.py`` file produces no AST entries — no crash."""
        (src_layout / "src" / "pkg" / "empty.py").write_text("", encoding="utf-8")
        (src_layout / "src" / "pkg" / "real.py").write_text(
            "def doit() -> None:\n    pass\n", encoding="utf-8"
        )
        _write_doc(
            src_layout,
            "api.md",
            "```python\ndef doit(x):\n    pass\n```\n",
        )

        # Empty file must not raise; drift in real.py is still detected.
        stale = find_stale_signatures(src_layout, ["doit"])

        assert any(s["actual_sig"] == "def doit() -> None" for s in stale)

    def test_same_bare_name_two_modules_qualified(self, tmp_path: Path) -> None:
        """Two modules with same function name — both qualified keys are tracked.

        If both signatures agree and the doc drifts from both, the stale entry's
        ``actual_sig`` matches the (only) shared AST signature — proving both
        qualified entries fed the comparison.
        """
        src = tmp_path / "src"
        (src / "a").mkdir(parents=True)
        (src / "b").mkdir(parents=True)
        (src / "a" / "__init__.py").write_text("")
        (src / "b" / "__init__.py").write_text("")
        (src / "a" / "foo.py").write_text("def parse() -> None:\n    pass\n")
        (src / "b" / "foo.py").write_text("def parse() -> None:\n    pass\n")

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "ref.md").write_text(
            "```python\ndef parse(drifted: int) -> int:\n    pass\n```\n"
        )

        stale = find_stale_signatures(tmp_path, ["parse"])

        # Both qualified entries disagree → stale, and actual_sig is the shared sig.
        assert any(s["actual_sig"] == "def parse() -> None" for s in stale)

    def test_nested_subpackages_distinct_keys(self, tmp_path: Path) -> None:
        """Same name nested in distinct subpackages — both qualified keys tracked."""
        src = tmp_path / "src" / "a"
        (src / "b").mkdir(parents=True)
        (src / "c").mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "b" / "__init__.py").write_text("")
        (src / "c" / "__init__.py").write_text("")
        (src / "b" / "parse.py").write_text("def parse() -> None:\n    pass\n")
        (src / "c" / "parse.py").write_text("def parse() -> None:\n    pass\n")

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "ref.md").write_text(
            "```python\ndef parse(drifted) -> int:\n    pass\n```\n"
        )

        stale = find_stale_signatures(tmp_path, ["parse"])

        # Both nested qualified entries disagree → stale emitted, actual_sig set.
        assert any(s["actual_sig"] == "def parse() -> None" for s in stale)


# ---------------------------------------------------------------------------
# Doc extractor edge cases (formerly tests/integration/test_extract_doc_signatures.py)
#
# Driven via ``find_stale_signatures``: the doc-extracted signature surfaces in
# the ``doc_sig`` and ``line`` fields of each ``StaleSignature`` record.
# ---------------------------------------------------------------------------


class TestFindStaleSignaturesDocExtraction:
    """Doc-side edge cases — exercises code-block signature extraction."""

    @pytest.fixture()
    def src_with_foo(self, tmp_path: Path) -> Path:
        """Project with a single ``foo`` function — doc signatures drift from this."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "mod.py").write_text(
            "def foo(real: str) -> str:\n    return real\n", encoding="utf-8"
        )
        return tmp_path

    def test_extracts_def_in_code_block(self, src_with_foo: Path) -> None:
        """A ``def`` inside a fenced code block is picked up as a doc signature."""
        _write_doc(
            src_with_foo,
            "api.md",
            "# API\n\n```python\ndef foo(x: int) -> str:\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_with_foo, ["foo"])

        records = _stale_for(stale, "foo")
        assert len(records) == 1
        assert records[0]["doc_sig"] == "def foo(x: int) -> str"
        assert records[0]["file"].endswith("api.md")
        assert isinstance(records[0]["line"], int)

    def test_extracts_class_in_code_block(self, tmp_path: Path) -> None:
        """A ``class`` inside a fenced code block is picked up."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "mod.py").write_text("class Bar:\n    pass\n", encoding="utf-8")

        _write_doc(
            tmp_path,
            "api.md",
            "# API\n\n```python\nclass Bar(SomeBase):\n    pass\n```\n",
        )

        stale = find_stale_signatures(tmp_path, ["Bar"])

        records = _stale_for(stale, "Bar")
        assert len(records) == 1
        assert records[0]["doc_sig"] == "class Bar(SomeBase)"

    def test_filters_symbols_not_in_set(self, tmp_path: Path) -> None:
        """Only the requested symbols are checked — others are ignored."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "mod.py").write_text(
            "def foo(a: int) -> None:\n    pass\ndef bar(b: int) -> None:\n    pass\n",
            encoding="utf-8",
        )
        _write_doc(
            tmp_path,
            "api.md",
            "```python\ndef foo(drifted):\n    pass\n"
            "def bar(drifted):\n    pass\n```\n",
        )

        stale = find_stale_signatures(tmp_path, ["bar"])

        symbols = {s["symbol"] for s in stale}
        assert "bar" in symbols
        assert "foo" not in symbols

    def test_ignores_def_outside_code_block(self, src_with_foo: Path) -> None:
        """A ``def`` outside any fenced block is not treated as a doc signature."""
        _write_doc(
            src_with_foo,
            "readme.md",
            "# Readme\n\ndef foo(x):\n    not in a code block\n",
        )

        stale = find_stale_signatures(src_with_foo, ["foo"])

        assert _stale_for(stale, "foo") == []

    def test_handles_multiple_code_blocks(self, tmp_path: Path) -> None:
        """Fenced blocks are independent — drifts in each one are caught."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "mod.py").write_text(
            "def alpha() -> None:\n    pass\ndef beta() -> None:\n    pass\n",
            encoding="utf-8",
        )
        _write_doc(
            tmp_path,
            "api.md",
            "```python\ndef alpha(x):\n    pass\n```\n\nSome text.\n\n"
            "```python\ndef beta(x):\n    pass\n```\n",
        )

        stale = find_stale_signatures(tmp_path, ["alpha", "beta"])

        symbols = {s["symbol"] for s in stale}
        assert symbols == {"alpha", "beta"}

    def test_empty_symbols_set_yields_nothing(self, src_with_foo: Path) -> None:
        """Passing an empty symbol list short-circuits — no stale records."""
        _write_doc(
            src_with_foo,
            "api.md",
            "```python\ndef foo(x):\n    pass\n```\n",
        )

        # Explicit empty list overrides the "None means all" fallback.
        assert find_stale_signatures(src_with_foo, []) == []

    def test_missing_doc_directory_no_crash(self, src_with_foo: Path) -> None:
        """No ``docs/`` directory and no README — no stale records, no crash."""
        assert find_stale_signatures(src_with_foo, ["foo"]) == []

    def test_empty_doc_file_no_crash(self, src_with_foo: Path) -> None:
        """An empty doc file produces no records."""
        _write_doc(src_with_foo, "empty.md", "")

        assert find_stale_signatures(src_with_foo, ["foo"]) == []

    def test_strips_trailing_colon_from_doc_sig(self, src_with_foo: Path) -> None:
        """The trailing ``:`` of a ``def`` line is stripped from ``doc_sig``."""
        _write_doc(
            src_with_foo,
            "api.md",
            "```python\ndef foo(x: int):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_with_foo, ["foo"])
        records = _stale_for(stale, "foo")

        assert len(records) == 1
        assert records[0]["doc_sig"] == "def foo(x: int)"

    def test_line_number_points_into_doc_file(self, src_with_foo: Path) -> None:
        """The ``line`` field reflects the def's position inside the doc file."""
        _write_doc(
            src_with_foo,
            "api.md",
            "line1\nline2\n```python\ndef foo(x):\n    pass\n```\n",
        )

        stale = find_stale_signatures(src_with_foo, ["foo"])
        records = _stale_for(stale, "foo")

        # ``def foo`` sits on line 4 of the doc file.
        assert records[0]["line"] == 4

    def test_unicode_decode_error_handled(self, src_with_foo: Path) -> None:
        """A binary doc file does not crash the extractor — yields no records."""
        docs = src_with_foo / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "binary.md").write_bytes(b"\x80\x81\x82")

        # Must not raise even though the bytes are not valid UTF-8.
        result = find_stale_signatures(src_with_foo, ["foo"])
        assert result == []

    def test_extracts_multiple_symbols_in_one_block(self, tmp_path: Path) -> None:
        """A code block with both a func and a class drifts both at once."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "mod.py").write_text(
            "def func_a() -> None:\n    pass\nclass ClassB:\n    pass\n",
            encoding="utf-8",
        )
        _write_doc(
            tmp_path,
            "api.md",
            "```python\ndef func_a(x):\n    pass\n"
            "class ClassB(Drift):\n    pass\n```\n",
        )

        stale = find_stale_signatures(tmp_path, ["func_a", "ClassB"])

        symbols = {s["symbol"] for s in stale}
        assert "func_a" in symbols
        assert "ClassB" in symbols
