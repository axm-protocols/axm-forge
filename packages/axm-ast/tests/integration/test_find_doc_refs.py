"""Split from ``test_doc_impact.py``."""

from pathlib import Path

from axm_ast.core.doc_impact import find_doc_refs


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
