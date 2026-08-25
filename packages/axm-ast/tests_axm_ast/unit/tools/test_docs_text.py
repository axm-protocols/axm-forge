from __future__ import annotations

from axm_ast.tools.docs_text import render_docs_text

_PAGE_FULL: dict[str, object] = {
    "path": "docs/guide.md",
    "content": "# Guide\n\nUse the thing carefully.\n",
}
_PAGE_TOC: dict[str, object] = {
    "path": "docs/guide.md",
    "headings": [
        {"level": 1, "text": "Guide"},
        {"level": 2, "text": "Setup"},
    ],
    "line_count": 12,
}
_PAGE_SUMMARY: dict[str, object] = {
    "path": "docs/guide.md",
    "headings": [{"level": 1, "text": "Guide"}],
    "summaries": {"Guide": "Use the thing carefully."},
    "line_count": 12,
}


def _data(pages: list[dict[str, object]]) -> dict[str, object]:
    return {
        "project": "demo",
        "readme": {"path": "README.md", "content": "# Demo\n\nHello.\n"},
        "mkdocs": {"path": "mkdocs.yml", "content": "site_name: Demo\n"},
        "tree": "docs/\n└── guide.md",
        "pages": pages,
    }


def test_header_has_project_and_page_count() -> None:
    """Header carries the ast_docs prefix, detail, project, and page count."""
    text = render_docs_text(_data([_PAGE_FULL]), "full")
    assert text.startswith("ast_docs | full | demo | 1 pages +2")


def test_full_reproduces_page_body_verbatim() -> None:
    """Full mode emits the complete page content without truncation."""
    text = render_docs_text(_data([_PAGE_FULL]), "full")
    assert "Use the thing carefully." in text
    assert "docs/guide.md" in text


def test_full_includes_readme_and_mkdocs() -> None:
    """README and mkdocs bodies are reproduced verbatim in full mode."""
    text = render_docs_text(_data([_PAGE_FULL]), "full")
    assert "Hello." in text
    assert "site_name: Demo" in text


def test_toc_renders_headings_not_body() -> None:
    """TOC mode renders the heading tree and line count, no body."""
    text = render_docs_text(_data([_PAGE_TOC]), "toc")
    assert "# Guide" in text
    assert "## Setup" in text
    assert "(12L)" in text


def test_summary_renders_first_sentences() -> None:
    """Summary mode renders per-heading first-sentence summaries."""
    text = render_docs_text(_data([_PAGE_SUMMARY]), "summary")
    assert "Guide: Use the thing carefully." in text


def test_no_pages_still_renders_header_and_extras() -> None:
    """An empty docs tree still yields the header plus README/mkdocs."""
    text = render_docs_text(_data([]), "toc")
    assert text.startswith("ast_docs | toc | demo | 0 pages +2")
    assert "README.md" in text
