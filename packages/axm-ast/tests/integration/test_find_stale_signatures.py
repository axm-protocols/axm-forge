"""Split from ``test_core_doc_impact.py``."""

from pathlib import Path

from axm_ast.core.doc_impact import find_stale_signatures
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
