"""Split from ``test_docs.py``."""

from pathlib import Path

from axm_ast.core.docs import discover_docs, format_docs


def _make_project(
    path: Path,
    *,
    readme: str | None = "# My Project\n\nHello world.\n",
    mkdocs: str | None = "site_name: My Project\nnav:\n  - Home: index.md\n",
    docs: dict[str, str] | None = None,
) -> Path:
    """Create a minimal project with optional README, mkdocs.yml, and docs/."""
    path.mkdir(parents=True, exist_ok=True)
    if readme is not None:
        (path / "README.md").write_text(readme)
    if mkdocs is not None:
        (path / "mkdocs.yml").write_text(mkdocs)
    if docs is not None:
        for name, content in docs.items():
            doc_path = path / "docs" / name
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content)
    return path


def test_format_text_output(tmp_path: Path) -> None:
    """Text format contains README + mkdocs + pages."""
    _make_project(
        tmp_path,
        docs={"index.md": "# Home\n"},
    )
    result = discover_docs(tmp_path)
    text = format_docs(result)
    assert "📖 README.md" in text
    assert "My Project" in text
    assert "⚙️" in text and "mkdocs.yml" in text
    assert "📄 docs/index.md" in text
    assert "# Home" in text


def test_format_no_readme_no_mkdocs(tmp_path: Path) -> None:
    """Handles missing README + mkdocs gracefully."""
    _make_project(tmp_path, readme=None, mkdocs=None, docs={"a.md": "# A\n"})
    result = discover_docs(tmp_path)
    text = format_docs(result)
    # Should not crash, and should include the docs page
    assert "📄 docs/a.md" in text
    assert "📖" not in text  # no README section


def test_format_tree_only(tmp_path: Path) -> None:
    """Tree-only mode shows tree but not file contents."""
    _make_project(
        tmp_path,
        docs={"index.md": "# Home\n", "guide.md": "# Guide\n"},
    )
    result = discover_docs(tmp_path)
    text = format_docs(result, tree_only=True)
    assert "docs/" in text or "index.md" in text
    # Should NOT include file contents
    assert "# Home" not in text
    assert "My Project" not in text
