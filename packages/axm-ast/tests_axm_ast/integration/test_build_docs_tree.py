"""Split from ``test_docs.py``."""

from pathlib import Path

from axm_ast.core.docs import build_docs_tree


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


class TestBuildDocsTree:
    """Test ASCII tree generation."""

    def test_tree_structure(self, tmp_path: Path) -> None:
        """Produces an ASCII tree with correct structure."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"index.md": "# Home\n", "tutorials/quickstart.md": "# QS\n"},
        )
        tree = build_docs_tree(tmp_path / "docs")
        assert tree is not None
        assert "index.md" in tree
        assert "tutorials" in tree
        assert "quickstart.md" in tree

    def test_tree_no_docs_dir(self, tmp_path: Path) -> None:
        """No docs/ → returns None."""
        tree = build_docs_tree(tmp_path / "docs")
        assert tree is None
