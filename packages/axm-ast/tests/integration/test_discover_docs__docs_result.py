"""Split from ``test_docs.py``."""

from pathlib import Path

from axm_ast.core.docs import DocsResult, discover_docs, format_docs_json


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


def test_format_json_structure(tmp_path: Path) -> None:
    """JSON format has correct keys and types."""
    _make_project(tmp_path, docs={"index.md": "# Home\n"})
    result = discover_docs(tmp_path)
    j: DocsResult = format_docs_json(result)
    assert "readme" in j
    assert "mkdocs" in j
    assert "pages" in j
    assert isinstance(j["pages"], list)
