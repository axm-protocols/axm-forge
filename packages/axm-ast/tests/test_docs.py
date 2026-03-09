"""TDD tests for axm-ast docs — documentation tree dump."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from axm_ast.core.docs import (
    build_docs_tree,
    discover_docs,
    format_docs,
    format_docs_json,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"


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


# ─── Unit: discover_docs ─────────────────────────────────────────────────────


class TestDiscoverDocs:
    """Test documentation discovery."""

    def test_discover_finds_readme(self, tmp_path: Path) -> None:
        """Finds README.md and returns its content."""
        _make_project(tmp_path, mkdocs=None, docs=None)
        result = discover_docs(tmp_path)
        assert result["readme"] is not None
        assert "My Project" in result["readme"]["content"]
        assert result["readme"]["path"] == "README.md"

    def test_discover_no_readme(self, tmp_path: Path) -> None:
        """No README → readme is None."""
        _make_project(tmp_path, readme=None, mkdocs=None, docs=None)
        result = discover_docs(tmp_path)
        assert result["readme"] is None

    def test_discover_readme_variants(self, tmp_path: Path) -> None:
        """Finds README.rst variant."""
        (tmp_path / "README.rst").write_text("My RST Readme\n=============\n")
        result = discover_docs(tmp_path)
        assert result["readme"] is not None
        assert result["readme"]["path"] == "README.rst"

    def test_discover_readme_priority(self, tmp_path: Path) -> None:
        """README.md takes priority over readme.md."""
        _make_project(tmp_path, mkdocs=None, docs=None)
        (tmp_path / "readme.md").write_text("# Lowercase\n")
        result = discover_docs(tmp_path)
        assert result["readme"]["path"] == "README.md"

    def test_discover_finds_mkdocs_yml(self, tmp_path: Path) -> None:
        """Finds mkdocs.yml and returns its content."""
        _make_project(tmp_path, readme=None, docs=None)
        result = discover_docs(tmp_path)
        assert result["mkdocs"] is not None
        assert "site_name" in result["mkdocs"]["content"]

    def test_discover_no_mkdocs(self, tmp_path: Path) -> None:
        """No mkdocs.yml → mkdocs is None."""
        _make_project(tmp_path, readme=None, mkdocs=None, docs=None)
        result = discover_docs(tmp_path)
        assert result["mkdocs"] is None

    def test_discover_finds_docs_pages(self, tmp_path: Path) -> None:
        """Finds all .md files in docs/."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"index.md": "# Home\n", "guide.md": "# Guide\n"},
        )
        result = discover_docs(tmp_path)
        paths = [p["path"] for p in result["pages"]]
        assert "docs/guide.md" in paths
        assert "docs/index.md" in paths

    def test_discover_no_docs_dir(self, tmp_path: Path) -> None:
        """No docs/ directory → pages is empty list."""
        _make_project(tmp_path, readme=None, mkdocs=None, docs=None)
        result = discover_docs(tmp_path)
        assert result["pages"] == []
        assert result["tree"] is None

    def test_discover_empty_docs_dir(self, tmp_path: Path) -> None:
        """Empty docs/ directory → pages is empty, tree exists."""
        _make_project(tmp_path, readme=None, mkdocs=None, docs=None)
        (tmp_path / "docs").mkdir()
        result = discover_docs(tmp_path)
        assert result["pages"] == []

    def test_discover_nested_docs(self, tmp_path: Path) -> None:
        """Finds markdown in nested directories."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={
                "index.md": "# Home\n",
                "tutorials/quickstart.md": "# QS\n",
                "howto/deploy.md": "# Deploy\n",
            },
        )
        result = discover_docs(tmp_path)
        paths = [p["path"] for p in result["pages"]]
        assert "docs/tutorials/quickstart.md" in paths
        assert "docs/howto/deploy.md" in paths

    def test_discover_skips_non_markdown(self, tmp_path: Path) -> None:
        """Skips images, .py files, etc. in docs/."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"index.md": "# Home\n"},
        )
        (tmp_path / "docs" / "logo.png").write_bytes(b"\x89PNG")
        (tmp_path / "docs" / "gen_ref_pages.py").write_text("# script\n")
        result = discover_docs(tmp_path)
        paths = [p["path"] for p in result["pages"]]
        assert "docs/index.md" in paths
        assert not any("logo.png" in p for p in paths)
        assert not any("gen_ref_pages.py" in p for p in paths)

    def test_discover_pages_sorted(self, tmp_path: Path) -> None:
        """Pages are returned in sorted order."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"z.md": "# Z\n", "a.md": "# A\n", "m.md": "# M\n"},
        )
        result = discover_docs(tmp_path)
        paths = [p["path"] for p in result["pages"]]
        assert paths == sorted(paths)


# ─── Unit: build_docs_tree ───────────────────────────────────────────────────


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


# ─── Unit: format ────────────────────────────────────────────────────────────


class TestFormatDocs:
    """Test text and JSON formatting."""

    def test_format_text_output(self, tmp_path: Path) -> None:
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

    def test_format_json_structure(self, tmp_path: Path) -> None:
        """JSON format has correct keys and types."""
        _make_project(tmp_path, docs={"index.md": "# Home\n"})
        result = discover_docs(tmp_path)
        j: dict[str, Any] = format_docs_json(result)
        assert "readme" in j
        assert "mkdocs" in j
        assert "pages" in j
        assert isinstance(j["pages"], list)

    def test_format_no_readme_no_mkdocs(self, tmp_path: Path) -> None:
        """Handles missing README + mkdocs gracefully."""
        _make_project(tmp_path, readme=None, mkdocs=None, docs={"a.md": "# A\n"})
        result = discover_docs(tmp_path)
        text = format_docs(result)
        # Should not crash, and should include the docs page
        assert "📄 docs/a.md" in text
        assert "📖" not in text  # no README section

    def test_format_tree_only(self, tmp_path: Path) -> None:
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


# ─── Functional: CLI ─────────────────────────────────────────────────────────


class TestCliDocs:
    """Functional tests for the CLI docs command."""

    def test_cli_docs_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI docs outputs text to stdout."""
        from axm_ast.cli import app

        with pytest.raises(SystemExit, match="0"):
            app(["docs", str(FIXTURES / "sample_pkg" / ".."), "--tree"])
        out = capsys.readouterr().out
        # Should have some output (tree at minimum or empty for fixtures)
        assert isinstance(out, str)

    def test_cli_docs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI docs --json outputs valid JSON."""
        from axm_ast.cli import app

        with pytest.raises(SystemExit, match="0"):
            app(["docs", str(FIXTURES / "sample_pkg" / ".."), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "pages" in data

    def test_cli_docs_tree_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI docs --tree outputs only tree."""
        from axm_ast.cli import app

        with pytest.raises(SystemExit, match="0"):
            app(["docs", str(FIXTURES / "sample_pkg" / ".."), "--tree"])
        out = capsys.readouterr().out
        assert isinstance(out, str)

    def test_cli_docs_dogfood(self) -> None:
        """Dogfood: discover_docs works on axm-ast project root."""
        project_root = Path(__file__).parent.parent
        result = discover_docs(project_root)
        assert result["readme"] is not None
        assert "axm-ast" in result["readme"]["content"]
        assert result["mkdocs"] is not None
        assert len(result["pages"]) >= 5  # we have 8+ pages


# ─── Unit: detail levels ─────────────────────────────────────────────────────


class TestDetailLevels:
    """Test progressive disclosure detail levels."""

    def test_docs_toc_returns_headings_only(self, tmp_path: Path) -> None:
        """detail=toc returns headings + line_count, no content."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={
                "index.md": "# Home\n\nWelcome.\n\n## Setup\n\nInstall it.\n",
                "guide.md": "# Guide\n\n## Getting Started\n\nHello.\n",
                "ref.md": "# Reference\n\n## API\n\nDetails.\n",
            },
        )
        result = discover_docs(tmp_path, detail="toc")
        pages = result["pages"]
        assert len(pages) == 3
        for page in pages:
            assert "headings" in page
            assert "line_count" in page
            assert "content" not in page
        # Check heading structure
        index_page = next(p for p in pages if "index" in p["path"])
        assert len(index_page["headings"]) == 2
        assert index_page["headings"][0] == {"level": 1, "text": "Home"}
        assert index_page["headings"][1] == {"level": 2, "text": "Setup"}

    def test_docs_summary_returns_first_sentences(self, tmp_path: Path) -> None:
        """detail=summary returns headings + summaries per section."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={
                "index.md": (
                    "# Home\n\nWelcome to the project.\n\n"
                    "## Setup\n\nInstall with pip.\n"
                ),
                "guide.md": "# Guide\n\nThis is the guide.\n",
                "ref.md": "# Reference\n\nAPI details here.\n",
            },
        )
        result = discover_docs(tmp_path, detail="summary")
        pages = result["pages"]
        assert len(pages) == 3
        for page in pages:
            assert "headings" in page
            assert "summaries" in page
            assert "line_count" in page
            assert "content" not in page
        index_page = next(p for p in pages if "index" in p["path"])
        assert "Home" in index_page["summaries"]
        assert index_page["summaries"]["Home"] == "Welcome to the project."
        assert index_page["summaries"]["Setup"] == "Install with pip."

    def test_docs_full_returns_content(self, tmp_path: Path) -> None:
        """detail=full returns content (same as current behavior)."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"index.md": "# Home\n\nWelcome.\n"},
        )
        result = discover_docs(tmp_path, detail="full")
        pages = result["pages"]
        assert len(pages) == 1
        assert "content" in pages[0]
        assert "# Home" in pages[0]["content"]

    def test_docs_default_detail_is_full(self, tmp_path: Path) -> None:
        """No detail param → same output as current (full content)."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"index.md": "# Home\n\nWelcome.\n"},
        )
        result = discover_docs(tmp_path)
        pages = result["pages"]
        assert len(pages) == 1
        assert "content" in pages[0]


# ─── Unit: pages filter ──────────────────────────────────────────────────────


class TestPagesFilter:
    """Test page name filtering."""

    def test_docs_pages_filter(self, tmp_path: Path) -> None:
        """Only matching pages returned, README/mkdocs always present."""
        _make_project(
            tmp_path,
            docs={
                "index.md": "# Home\n",
                "architecture.md": "# Architecture\n",
                "howto/deploy.md": "# Deploy\n",
                "howto/install.md": "# Install\n",
                "reference/api.md": "# API\n",
            },
        )
        result = discover_docs(tmp_path, pages=["architecture"])
        paths = [p["path"] for p in result["pages"]]
        assert any("architecture" in p for p in paths)
        assert not any("index.md" in p for p in paths)
        assert not any("deploy" in p for p in paths)
        # README and mkdocs are always included (separate keys)
        assert result["readme"] is not None
        assert result["mkdocs"] is not None

    def test_docs_pages_filter_case_insensitive(self, tmp_path: Path) -> None:
        """pages filter is case-insensitive."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"architecture.md": "# Architecture\n"},
        )
        result = discover_docs(tmp_path, pages=["ARCH"])
        paths = [p["path"] for p in result["pages"]]
        assert any("architecture" in p for p in paths)


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases for progressive disclosure."""

    def test_docs_empty_docs_dir_with_detail(self, tmp_path: Path) -> None:
        """Empty docs dir → empty pages, README/mkdocs still returned."""
        _make_project(tmp_path, docs=None)
        (tmp_path / "docs").mkdir()
        result = discover_docs(tmp_path, detail="toc")
        assert result["pages"] == []
        assert result["readme"] is not None
        assert result["mkdocs"] is not None

    def test_docs_page_with_no_headings(self, tmp_path: Path) -> None:
        """Page with no headings → headings: [], still included."""
        _make_project(
            tmp_path,
            readme=None,
            mkdocs=None,
            docs={"plain.md": "Just some body text.\nNo headings here.\n"},
        )
        result = discover_docs(tmp_path, detail="toc")
        assert len(result["pages"]) == 1
        assert result["pages"][0]["headings"] == []
        assert result["pages"][0]["line_count"] > 0

    def test_docs_pages_filter_matches_nothing(self, tmp_path: Path) -> None:
        """Filter matches nothing → empty pages, README/mkdocs still returned."""
        _make_project(
            tmp_path,
            docs={"index.md": "# Home\n"},
        )
        result = discover_docs(tmp_path, pages=["nonexistent"])
        assert result["pages"] == []
        assert result["readme"] is not None
        assert result["mkdocs"] is not None
