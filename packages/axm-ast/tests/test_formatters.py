"""Test formatters — output formatting at all detail levels.

TDD: Tests written first, then formatters.py implementation.
"""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.formatters import format_json, format_mermaid, format_text

FIXTURES = Path(__file__).parent / "fixtures"
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

    def test_empty_package(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        pkg = analyze_package(empty)
        output = format_text(pkg, detail="summary")
        assert isinstance(output, str)


# ─── format_json ─────────────────────────────────────────────────────────────


class TestFormatJson:
    """Tests for JSON output."""

    def test_returns_dict(self):
        pkg = analyze_package(SAMPLE_PKG)
        result = format_json(pkg, detail="summary")
        assert isinstance(result, dict)

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

    def test_returns_string(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_mermaid(pkg)
        assert isinstance(output, str)

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
