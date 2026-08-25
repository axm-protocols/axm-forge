"""TDD tests for axm-ast docs — documentation tree dump."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.docs import (
    discover_docs,
    extract_headings,
)


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


# ─── Published limits page (doc_impact) ──────────────────────────────────────

_PACKAGE_ROOT = Path(__file__).parents[2]
_LIMITS_PAGE = "explanation/doc_impact_limits.md"
_LIMITS_TITLE = "Limites — ce que cet outil ne détecte pas"


def _limits_section() -> str:
    """Return the lowercased body of the limits section of the published page."""
    page = _PACKAGE_ROOT / "docs" / _LIMITS_PAGE
    lines = page.read_text(encoding="utf-8").splitlines()
    starts = [
        i for i, line in enumerate(lines) if line.lstrip("#").strip() == _LIMITS_TITLE
    ]
    assert starts, f"heading {_LIMITS_TITLE!r} not found in docs/{_LIMITS_PAGE}"
    start = starts[0]
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    body: list[str] = []
    for line in lines[start + 1 :]:
        hashes = len(line) - len(line.lstrip("#"))
        if line.startswith("#") and hashes <= level:
            break
        body.append(line)
    return "\n".join(body).lower()


@pytest.mark.integration
def test_limits_page_is_discovered_with_expected_title() -> None:
    """AC2: discover_docs surfaces the limits page under its exact title."""
    result = discover_docs(_PACKAGE_ROOT, detail="full", pages=None)

    page = next(
        (p for p in result["pages"] if p["path"].endswith(_LIMITS_PAGE)),
        None,
    )
    assert page is not None, f"{_LIMITS_PAGE} not discovered under docs/"

    headings = extract_headings(page["content"])
    assert any(h["text"] == _LIMITS_TITLE for h in headings)


@pytest.mark.integration
def test_limits_section_states_the_three_consequences() -> None:
    """AC3: the section spells out the three consequences of lexical matching."""
    body = _limits_section()

    for needle in (
        "sémantique",
        "inchangée",
        "name-drop",
        "undocumented",
        "oracle",
        "non-régression",
    ):
        assert needle in body, f"missing {needle!r} in the limits section"


@pytest.mark.integration
def test_limits_section_gives_the_prescriptive_rule() -> None:
    """AC4: the section says what to do when semantics change at same name."""
    body = _limits_section()

    assert "chaque page" in body
    assert "à la main" in body


@pytest.mark.integration
def test_limits_page_is_declared_in_mkdocs_nav() -> None:
    """AC5: the page is declared in mkdocs.yml, hence not orphaned."""
    mkdocs = (_PACKAGE_ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert _LIMITS_PAGE in mkdocs
