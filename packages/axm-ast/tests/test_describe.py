"""Tests for DescribeTool — API surface description with detail levels."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture()
def tool() -> DescribeTool:
    """Provide a fresh DescribeTool instance."""
    return DescribeTool()


@pytest.fixture()
def demo_pkg(tmp_path: Path) -> Path:
    """Create a multi-module package for describe tests."""
    pkg = tmp_path / "describedemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Describe demo."""\n')
    (pkg / "alpha.py").write_text(
        '"""Alpha module."""\n\n'
        "def alpha_one() -> str:\n"
        '    """First."""\n'
        '    return "a1"\n\n\n'
        "def alpha_two(x: int) -> int:\n"
        '    """Second."""\n'
        "    return x * 2\n"
    )
    (pkg / "beta.py").write_text(
        '"""Beta module."""\n\n'
        "class BetaClass:\n"
        '    """A class."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run."""\n'
    )
    return pkg


# ─── Tool identity ──────────────────────────────────────────────────────────


class TestDescribeToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: DescribeTool) -> None:
        assert tool.name == "ast_describe"

    def test_has_agent_hint(self, tool: DescribeTool) -> None:
        assert tool.agent_hint


# ─── TOC mode ────────────────────────────────────────────────────────────────


class TestDescribeToolToc:
    """Tests for detail='toc' mode."""

    def test_toc_returns_module_names_and_counts(
        self, tool: DescribeTool, demo_pkg: Path
    ) -> None:
        result = tool.execute(path=str(demo_pkg), detail="toc")
        assert result.success is True
        assert "modules" in result.data
        assert "module_count" in result.data
        for entry in result.data["modules"]:
            assert "name" in entry
            assert "symbol_count" in entry
            # Must NOT contain full function/class arrays
            assert "functions" not in entry
            assert "classes" not in entry

    def test_toc_module_count_matches(self, tool: DescribeTool, demo_pkg: Path) -> None:
        result = tool.execute(path=str(demo_pkg), detail="toc")
        assert result.data["module_count"] == len(result.data["modules"])


# ─── Module filtering ────────────────────────────────────────────────────────


class TestDescribeToolFiltering:
    """Tests for modules=[...] filtering."""

    def test_filter_single_module(self, tool: DescribeTool, demo_pkg: Path) -> None:
        result = tool.execute(path=str(demo_pkg), modules=["alpha"])
        assert result.success is True
        for mod in result.data["modules"]:
            assert "alpha" in mod["name"].lower()

    def test_filter_no_match_returns_empty(
        self, tool: DescribeTool, demo_pkg: Path
    ) -> None:
        result = tool.execute(path=str(demo_pkg), modules=["nonexistent_xyz"])
        assert result.success is True
        assert result.data["module_count"] == 0

    def test_filter_combined_with_toc(self, tool: DescribeTool, demo_pkg: Path) -> None:
        result = tool.execute(path=str(demo_pkg), detail="toc", modules=["beta"])
        assert result.success is True
        for entry in result.data["modules"]:
            assert "beta" in entry["name"].lower()
            assert "functions" not in entry


# ─── Detail levels ───────────────────────────────────────────────────────────


class TestDescribeToolDetailLevels:
    """Tests for various detail levels."""

    def test_describe_default_detail(self, tool: DescribeTool, demo_pkg: Path) -> None:
        """Default detail (no explicit arg) should behave like summary."""
        result = tool.execute(path=str(demo_pkg))
        assert result.success is True
        for mod in result.data["modules"]:
            for fn in mod.get("functions", []):
                assert "summary" not in fn

    def test_detailed_includes_docstrings(
        self, tool: DescribeTool, demo_pkg: Path
    ) -> None:
        result = tool.execute(path=str(demo_pkg), detail="detailed")
        assert result.success is True
        alpha_mod = next(
            (m for m in result.data["modules"] if m["name"] == "alpha"), None
        )
        assert alpha_mod is not None
        fn = next((f for f in alpha_mod["functions"] if f["name"] == "alpha_one"), None)
        assert fn is not None
        assert "summary" in fn

    def test_summary_excludes_docstrings(
        self, tool: DescribeTool, demo_pkg: Path
    ) -> None:
        result = tool.execute(path=str(demo_pkg), detail="summary")
        assert result.success is True
        for mod in result.data["modules"]:
            for fn in mod.get("functions", []):
                assert "summary" not in fn


# ─── Compress mode ───────────────────────────────────────────────────────────


class TestDescribeToolCompress:
    """Tests for compress=True mode."""

    def test_compress_returns_text(self, tool: DescribeTool, demo_pkg: Path) -> None:
        result = tool.execute(path=str(demo_pkg), compress=True)
        assert result.success is True
        assert "compressed" in result.data
        assert isinstance(result.data["compressed"], str)
        assert result.data["module_count"] > 0


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestDescribeToolEdgeCases:
    """Edge cases for DescribeTool."""

    def test_bad_path(self, tool: DescribeTool) -> None:
        result = tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False

    def test_empty_package(self, tool: DescribeTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert result.data["module_count"] == 0
