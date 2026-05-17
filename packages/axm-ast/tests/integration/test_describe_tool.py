"""Tests for DescribeTool — API surface description with detail levels."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.describe import DescribeTool
from tests.integration._helpers import _assert_tool_result


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


class TestDescribeToolEdgeCases:
    """Edge cases for DescribeTool (filesystem I/O)."""

    def test_empty_package(self, tool: DescribeTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert result.data["module_count"] == 0


@pytest.fixture()
def tool__from_describe_text() -> DescribeTool:
    return DescribeTool()


def test_empty_package(tool__from_describe_text: DescribeTool, tmp_path: Path) -> None:
    pkg_dir = tmp_path / "empty_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    result = tool__from_describe_text.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    assert result.text.startswith("ast_describe | summary | 1 modules")


def test_module_with_only_classes(
    tool__from_describe_text: DescribeTool, tmp_path: Path
) -> None:
    pkg_dir = tmp_path / "cls_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "shapes.py").write_text(
        "class Circle:\n    pass\n\nclass Square:\n    pass\n"
    )
    result = tool__from_describe_text.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    assert "Circle" in result.text or "Square" in result.text


def test_no_docstring_on_module(
    tool__from_describe_text: DescribeTool, tmp_path: Path
) -> None:
    pkg_dir = tmp_path / "nodoc_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "bare.py").write_text("def hello(): pass\n")
    result = tool__from_describe_text.execute(path=str(pkg_dir), detail="detailed")
    assert result.success
    assert result.text is not None
    # Header should have module name without em-dash suffix
    for line in result.text.splitlines():
        if line.startswith("## ") and "bare" in line:
            assert "\u2014" not in line
            break


def test_very_long_signature(
    tool__from_describe_text: DescribeTool, tmp_path: Path
) -> None:
    pkg_dir = tmp_path / "long_sig_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    params = ", ".join(f"p{i}: int = 0" for i in range(12))
    (pkg_dir / "wide.py").write_text(f"def big_func({params}): pass\n")
    result = tool__from_describe_text.execute(path=str(pkg_dir), detail="summary")
    assert result.success
    assert result.text is not None
    # Full signature on one line (no wrapping)
    sig_lines = [line for line in result.text.splitlines() if "big_func" in line]
    assert len(sig_lines) == 1
    assert "p11" in sig_lines[0]


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def test_describe_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.cache.get_package",
        side_effect=RuntimeError("describe boom"),
    )
    result = DescribeTool().execute(path=str(pkg))
    assert result.success is False
    assert "describe boom" in (result.error or "")


class TestDescribeToolIntegration:
    """Tests for ast_describe tool."""

    def test_execute_returns_modules(self, sample_project: Path) -> None:

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True
        assert "modules" in result.data

    def test_execute_compress_mode(self, sample_project: Path) -> None:

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), compress=True)
        assert result.success is True
        assert "compressed" in result.data

    def test_execute_detailed_includes_docstrings(self, sample_project: Path) -> None:

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), detail="detailed"
        )
        assert result.success is True
        # Find core module with greet function
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None, "core module not found"
        greet_fn = next(
            (f for f in core_mod["functions"] if f["name"] == "greet"), None
        )
        assert greet_fn is not None, "greet function not found"
        assert "summary" in greet_fn
        assert greet_fn["summary"] == "Say hello."

    def test_execute_summary_excludes_docstrings(self, sample_project: Path) -> None:

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), detail="summary"
        )
        assert result.success is True
        for mod in result.data["modules"]:
            for fn in mod.get("functions", []):
                msg = f"summary unexpectedly present in {fn['name']}"
                assert "summary" not in fn, msg

    def test_execute_default_detail_is_summary(self, sample_project: Path) -> None:

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # Default should return signatures only (detail="summary"), no docstrings
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None
        greet_fn = next(
            (f for f in core_mod["functions"] if f["name"] == "greet"), None
        )
        assert greet_fn is not None
        assert "signature" in greet_fn
        assert "summary" not in greet_fn

    # --- TOC mode (AXM-131) ---

    def test_describe_tool_toc(self, sample_project: Path) -> None:
        """AC1: detail='toc' returns module list with counts."""

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), detail="toc")
        assert result.success is True
        assert "modules" in result.data
        assert "module_count" in result.data
        entry = result.data["modules"][0]
        assert "name" in entry
        assert "symbol_count" in entry
        assert "function_count" in entry
        assert "class_count" in entry
        # Must NOT have functions/classes arrays
        assert "functions" not in entry
        assert "classes" not in entry

    def test_describe_tool_modules_filter(self, sample_project: Path) -> None:
        """AC3: modules=['core'] returns only core modules."""

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), modules=["core"]
        )
        assert result.success is True
        for mod in result.data["modules"]:
            assert "core" in mod["name"].lower()

    def test_describe_tool_toc_plus_filter(self, sample_project: Path) -> None:
        """AC4: detail='toc' + modules=['core'] combines both."""

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            detail="toc",
            modules=["core"],
        )
        assert result.success is True
        for entry in result.data["modules"]:
            assert "core" in entry["name"].lower()
            assert "functions" not in entry

    def test_describe_tool_default_unchanged(self, sample_project: Path) -> None:
        """AC5: default behavior unchanged (regression)."""

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # Must have full module data with functions/classes arrays
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None
        assert "functions" in core_mod
        assert "classes" in core_mod

    def test_describe_tool_filter_no_match(self, sample_project: Path) -> None:
        """Edge: non-matching filter returns empty list, success=True."""

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            modules=["nonexistent_xyz"],
        )
        assert result.success is True
        assert result.data["module_count"] == 0
