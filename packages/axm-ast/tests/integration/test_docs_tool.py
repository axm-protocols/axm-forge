"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path
from unittest.mock import MagicMock

from tests.integration._helpers import _assert_tool_result


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def test_docs_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:
    from axm_ast.tools.docs import DocsTool

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.docs.discover_docs",
        side_effect=RuntimeError("docs boom"),
    )
    result = DocsTool().execute(path=str(pkg))
    assert result.success is False
    assert "docs boom" in (result.error or "")


class TestDocsToolIntegration:
    """Tests for ast_docs tool."""

    def test_docs_returns_readme(self, sample_project: Path) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project))
        _assert_tool_result(result)
        assert result.success is True
        assert "readme" in result.data

    # --- Progressive disclosure (detail + pages) ---

    def test_docs_toc_returns_headings_not_content(self, sample_project: Path) -> None:
        """detail='toc' returns headings + line_count, NOT content."""
        # Create docs/ with a markdown file
        docs = sample_project / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide\n\n## Getting Started\n\nSome text.\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="toc")
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        page = pages[0]
        assert "headings" in page
        assert "line_count" in page
        assert "content" not in page

    def test_docs_summary_returns_summaries(self, sample_project: Path) -> None:
        """detail='summary' returns headings + first sentences."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "api.md").write_text(
            "# API Reference\n\nFull API docs.\n\n"
            "## Functions\n\nAll public functions.\n"
        )

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="summary")
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        page = pages[0]
        assert "headings" in page
        assert "summaries" in page
        assert "content" not in page

    def test_docs_full_returns_content(self, sample_project: Path) -> None:
        """detail='full' (default) returns full content."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "intro.md").write_text("# Intro\n\nHello.\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project))
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        assert "content" in pages[0]

    def test_docs_pages_filter(self, sample_project: Path) -> None:
        """pages=['guide'] filters to matching pages only."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "guide.md").write_text("# Guide\n")
        (docs / "api.md").write_text("# API\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), pages=["guide"])
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) == 1
        assert "guide" in pages[0]["path"]

    def test_docs_toc_with_pages_filter(self, sample_project: Path) -> None:
        """detail='toc' + pages=['api'] combines both filters."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "guide.md").write_text("# Guide\n")
        (docs / "api.md").write_text("# API\n\n## Endpoints\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="toc", pages=["api"])
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) == 1
        assert "content" not in pages[0]
        assert len(pages[0]["headings"]) == 2
