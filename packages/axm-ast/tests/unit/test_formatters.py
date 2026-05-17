"""Test formatters — output formatting at all detail levels.

TDD: Tests written first, then formatters.py implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import (
    format_compressed,
    format_json,
    format_mermaid,
    format_text,
)
from axm_ast.models.nodes import PackageInfo

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── format_text ─────────────────────────────────────────────────────────────


class TestFormatText:
    """Tests for human-readable text output."""

    def test_summary_level(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_text(pkg, detail="summary")
        assert isinstance(output, str)
        assert "sample_pkg" in output
        assert "greet" in output

    def test_detailed_level(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_text(pkg, detail="detailed")
        # Detailed should include docstrings
        assert "greeting" in output.lower() or "greet" in output

    def test_budget_truncation(self):
        pkg = analyze_package(SAMPLE_PKG)
        detailed = format_text(pkg, detail="detailed")
        truncated = format_text(pkg, detail="detailed", budget=10)
        assert len(truncated.splitlines()) <= len(detailed.splitlines())


# ─── format_json ─────────────────────────────────────────────────────────────


class TestFormatJson:
    """Tests for JSON output."""

    def test_has_package_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        result = format_json(pkg, detail="summary")
        assert result["name"] == "sample_pkg"

    def test_has_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
        result = format_json(pkg, detail="summary")
        assert "modules" in result
        assert len(result["modules"]) >= 3

    def test_detailed_includes_docstrings(self):
        pkg = analyze_package(SAMPLE_PKG)
        result = format_json(pkg, detail="detailed")
        # At least one function should have a summary (parsed from docstring)
        has_summary = False
        for mod in result["modules"]:
            for fn in mod.get("functions", []):
                if fn.get("summary"):
                    has_summary = True
        assert has_summary


# ─── format_mermaid ──────────────────────────────────────────────────────────


class TestFormatMermaid:
    """Tests for Mermaid diagram output."""

    def test_contains_graph_keyword(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_mermaid(pkg)
        assert "graph" in output or "flowchart" in output

    def test_contains_module_names(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_mermaid(pkg)
        assert "utils" in output or "sample_pkg" in output


# ─── format_toc ──────────────────────────────────────────────────────────────


class TestFormatToc:
    """Tests for TOC output (AXM-131)."""

    def test_toc_returns_module_list(self):
        """format_toc returns list of dicts with expected keys."""
        from axm_ast.formatters import format_toc

        pkg = analyze_package(SAMPLE_PKG)
        toc = format_toc(pkg)
        assert isinstance(toc, list)
        assert len(toc) >= 1
        entry = toc[0]
        assert "name" in entry
        assert "docstring" in entry
        assert "symbol_count" in entry
        assert "function_count" in entry
        assert "class_count" in entry

    def test_toc_no_symbols(self):
        """TOC entries must NOT contain functions or classes arrays."""
        from axm_ast.formatters import format_toc

        pkg = analyze_package(SAMPLE_PKG)
        toc = format_toc(pkg)
        for entry in toc:
            assert "functions" not in entry
            assert "classes" not in entry

    def test_toc_counts_correct(self):
        """symbol_count = function_count + class_count."""
        from axm_ast.formatters import format_toc

        pkg = analyze_package(SAMPLE_PKG)
        toc = format_toc(pkg)
        for entry in toc:
            assert (
                entry["symbol_count"] == entry["function_count"] + entry["class_count"]
            )


# ─── filter_modules ──────────────────────────────────────────────────────────


class TestFilterModules:
    """Tests for module filtering (AXM-131)."""

    def test_filter_modules_none(self):
        """None filter returns all modules."""
        from axm_ast.formatters import filter_modules

        pkg = analyze_package(SAMPLE_PKG)
        result = filter_modules(pkg, None)
        assert len(result.modules) == len(pkg.modules)

    def test_filter_modules_empty_list(self):
        """Empty list treated as None — returns all modules."""
        from axm_ast.formatters import filter_modules

        pkg = analyze_package(SAMPLE_PKG)
        result = filter_modules(pkg, [])
        assert len(result.modules) == len(pkg.modules)

    def test_filter_modules_substring(self):
        """Filter by substring returns matching modules only."""
        from axm_ast.formatters import filter_modules

        pkg = analyze_package(SAMPLE_PKG)
        result = filter_modules(pkg, ["utils"])
        assert len(result.modules) >= 1
        from axm_ast.core.analyzer import module_dotted_name

        for mod in result.modules:
            assert "utils" in module_dotted_name(mod.path, result.root).lower()

    def test_filter_modules_case_insensitive(self):
        """Case-insensitive matching."""
        from axm_ast.formatters import filter_modules

        pkg = analyze_package(SAMPLE_PKG)
        lower = filter_modules(pkg, ["utils"])
        upper = filter_modules(pkg, ["UTILS"])
        assert len(lower.modules) == len(upper.modules)

    def test_filter_modules_no_match(self):
        """Non-matching filter returns empty modules list."""
        from axm_ast.formatters import filter_modules

        pkg = analyze_package(SAMPLE_PKG)
        result = filter_modules(pkg, ["nonexistent_xyz"])
        assert len(result.modules) == 0


# ─── Compress format tests (merged from test_compress.py) ──────────────────


class TestFormatCompressedUnit:
    """Test the compressed output format."""

    @pytest.fixture()
    def pkg(self) -> PackageInfo:
        """Analyze the sample package."""
        return analyze_package(SAMPLE_PKG)

    def test_returns_string(self, pkg: PackageInfo) -> None:
        """Returns a non-empty string."""
        output = format_compressed(pkg)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_signatures_present(self, pkg: PackageInfo) -> None:
        """All public function signatures should appear."""
        output = format_compressed(pkg)
        assert "def greet(name: str) -> str" in output
        assert "def resolve_path(p: str) -> Path" in output

    def test_first_docstring_line_only(self, pkg: PackageInfo) -> None:
        """Only the first docstring line is kept."""
        output = format_compressed(pkg)
        assert "Return a greeting message." in output
        # Full multi-line docstrings should not appear
        assert output.count('"""') % 2 == 0  # balanced quotes

    def test_no_function_bodies(self, pkg: PackageInfo) -> None:
        """No function body code (return, raise, etc.)."""
        output = format_compressed(pkg)
        # The sample_pkg greet() returns f"Hello, {name}!"
        assert "Hello, {name}" not in output

    def test_class_present(self, pkg: PackageInfo) -> None:
        """Public classes should appear with their base classes."""
        output = format_compressed(pkg)
        assert "class Calculator" in output

    def test_class_methods_as_stubs(self, pkg: PackageInfo) -> None:
        """Class methods appear as signatures."""
        output = format_compressed(pkg)
        assert "def add(self" in output

    def test_private_symbols_excluded(self, pkg: PackageInfo) -> None:
        """Private symbols not in __all__ are excluded."""
        output = format_compressed(pkg)
        assert "_internal_helper" not in output
        assert "_InternalClass" not in output

    def test_module_docstring_present(self, pkg: PackageInfo) -> None:
        """Module-level docstrings appear."""
        output = format_compressed(pkg)
        assert "A sample Python module" in output

    def test_absolute_imports_dropped(self, pkg: PackageInfo) -> None:
        """Absolute imports are dropped."""
        output = format_compressed(pkg)
        assert "from pathlib import" not in output
        assert "from typing import" not in output

    def test_all_exports_shown(self, pkg: PackageInfo) -> None:
        """__all__ list is preserved if it exists."""
        output = format_compressed(pkg)
        assert "__all__" in output


class TestCompressFunctional:
    """Functional tests comparing compress to other formats."""

    def test_compress_shorter_than_full(self) -> None:
        """Compressed output is significantly shorter than full."""
        pkg = analyze_package(SAMPLE_PKG)
        full = format_text(pkg, detail="detailed")
        compressed = format_compressed(pkg)
        assert len(compressed) < len(full)
