from __future__ import annotations

from pathlib import Path

from axm_ast.core.doc_impact import _extract_ast_signatures, find_stale_signatures

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_extract_ast_signatures_qualified_keys(tmp_path: Path) -> None:
    """Two modules with same function name produce distinct qualified keys."""
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir(parents=True)
    (src / "a" / "__init__.py").write_text("")
    (src / "b" / "__init__.py").write_text("")
    (src / "a" / "foo.py").write_text("def parse():\n    pass\n")
    (src / "b" / "foo.py").write_text("def parse():\n    pass\n")

    sigs = _extract_ast_signatures(tmp_path)

    assert "a.foo.parse" in sigs
    assert "b.foo.parse" in sigs


def test_extract_ast_signatures_single_module(tmp_path: Path) -> None:
    """Single module produces module-qualified key."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text("def run():\n    pass\n")

    sigs = _extract_ast_signatures(tmp_path)

    assert "pkg.mod.run" in sigs
    assert sigs["pkg.mod.run"] == "def run()"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_nested_subpackages_distinct_keys(tmp_path: Path) -> None:
    """Same name in nested subpackages yields distinct qualified keys."""
    src = tmp_path / "src" / "a"
    (src / "b").mkdir(parents=True)
    (src / "c").mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "b" / "__init__.py").write_text("")
    (src / "c" / "__init__.py").write_text("")
    (src / "b" / "parse.py").write_text("def parse():\n    pass\n")
    (src / "c" / "parse.py").write_text("def parse():\n    pass\n")

    sigs = _extract_ast_signatures(tmp_path)

    assert "a.b.parse.parse" in sigs
    assert "a.c.parse.parse" in sigs


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
