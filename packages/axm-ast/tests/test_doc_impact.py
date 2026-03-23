"""TDD tests for axm-ast doc_impact — doc refs, undocumented symbols, stale sigs."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.doc_impact import (
    analyze_doc_impact,
    find_doc_refs,
    find_stale_signatures,
    find_undocumented,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


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


# ─── Unit: find_doc_refs ─────────────────────────────────────────────────────


class TestFindDocRefs:
    """Test documentation reference discovery for symbols."""

    def test_find_doc_refs_found(self, tmp_path: Path) -> None:
        """README mentioning 'MyClass' → doc_refs contains README.md with line."""
        root = _make_pkg(
            tmp_path,
            src_code=('class MyClass:\n    """A class."""\n    pass\n'),
            readme="# My Project\n\nUse `MyClass` to do things.\n",
        )
        refs = find_doc_refs(root, ["MyClass"])
        assert len(refs) > 0
        my_refs = refs["MyClass"]
        assert any("README.md" in r["file"] for r in my_refs)
        # Each ref should include a line number
        readme_ref = next(r for r in my_refs if "README.md" in r["file"])
        assert "line" in readme_ref
        assert readme_ref["line"] > 0

    def test_find_doc_refs_not_found(self, tmp_path: Path) -> None:
        """README without mention → doc_refs empty for that symbol."""
        root = _make_pkg(
            tmp_path,
            src_code=('class MyClass:\n    """A class."""\n    pass\n'),
            readme="# My Project\n\nNo class mentions here.\n",
        )
        refs = find_doc_refs(root, ["MyClass"])
        assert refs["MyClass"] == []

    def test_find_doc_refs_multiple_files(self, tmp_path: Path) -> None:
        """README + docs/ref.md mentioning the symbol → 2 entries in mentioned_in."""
        root = _make_pkg(
            tmp_path,
            src_code=('class Widget:\n    """A widget."""\n    pass\n'),
            readme="# Project\n\nSee `Widget` for details.\n",
            docs={"ref.md": "# Reference\n\n## Widget\n\nThe `Widget` class.\n"},
        )
        refs = find_doc_refs(root, ["Widget"])
        files = [r["file"] for r in refs["Widget"]]
        assert len(files) >= 2
        assert any("README.md" in f for f in files)
        assert any("ref.md" in f for f in files)


# ─── Unit: find_undocumented ─────────────────────────────────────────────────


class TestFindUndocumented:
    """Test detection of symbols absent from documentation."""

    def test_undocumented_detected(self, tmp_path: Path) -> None:
        """Symbol absent from any doc → present in undocumented."""
        root = _make_pkg(
            tmp_path,
            src_code=('def secret_func() -> None:\n    """Secret."""\n    pass\n'),
            readme="# My Project\n\nNothing about secret_func here.\n",
            docs={"guide.md": "# Guide\n\nNo mention of secret_func.\n"},
        )
        # find_doc_refs returns empty for secret_func → it's undocumented
        refs = find_doc_refs(root, ["secret_func"])
        undocumented = find_undocumented(refs)
        assert "secret_func" in undocumented


# ─── Unit: find_stale_signatures ─────────────────────────────────────────────


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


# ─── Functional: analyze_doc_impact ──────────────────────────────────────────


class TestAnalyzeDocImpact:
    """Functional tests for the full doc impact pipeline."""

    def test_analyze_doc_impact_full(self, tmp_path: Path) -> None:
        """sample_pkg with README + docs/ → complete return structure."""
        root = _make_pkg(
            tmp_path,
            src_code=(
                "class Documented:\n"
                '    """A documented class."""\n'
                "    pass\n"
                "\n"
                "def undoc_func() -> None:\n"
                '    """Not in docs."""\n'
                "    pass\n"
                "\n"
                "def stale_func(a: int, b: int) -> int:\n"
                '    """Stale in docs."""\n'
                "    return a + b\n"
            ),
            readme=(
                "# Project\n\n"
                "Use `Documented` for things.\n\n"
                "```python\n"
                "def stale_func(a):\n"
                "    ...\n"
                "```\n"
            ),
            docs={"api.md": "# API\n\n## Documented\n\nThe `Documented` class.\n"},
        )
        symbols = ["Documented", "undoc_func", "stale_func"]
        result = analyze_doc_impact(root, symbols)

        # Structure check
        assert "doc_refs" in result
        assert "undocumented" in result
        assert "stale_signatures" in result

        # Documented → has refs
        assert len(result["doc_refs"]["Documented"]) >= 1

        # undoc_func → undocumented
        assert "undoc_func" in result["undocumented"]

        # stale_func → stale signature
        assert any(s["symbol"] == "stale_func" for s in result["stale_signatures"])


# ─── Functional: DocImpactTool ───────────────────────────────────────────────


class TestDocImpactTool:
    """Test the MCP tool wrapper."""

    def test_tool_execute(self, tmp_path: Path) -> None:
        """DocImpactTool.execute on sample_pkg → ToolResult success."""
        from axm_ast.tools.doc_impact import DocImpactTool

        root = _make_pkg(
            tmp_path,
            src_code=('class MyClass:\n    """A class."""\n    pass\n'),
            readme="# Project\n\nUse `MyClass`.\n",
        )
        tool = DocImpactTool()
        result = tool.execute(path=str(root), symbols=["MyClass"])

        assert result.success is True
        assert result.data is not None
        assert "doc_refs" in result.data
        assert "undocumented" in result.data
        assert "stale_signatures" in result.data
