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

    def test_full_level(self):
        pkg = analyze_package(SAMPLE_PKG)
        output = format_text(pkg, detail="full")
        # Full should include imports
        assert "import" in output.lower()

    def test_budget_truncation(self):
        pkg = analyze_package(SAMPLE_PKG)
        full = format_text(pkg, detail="full")
        truncated = format_text(pkg, detail="full", budget=10)
        assert len(truncated.splitlines()) <= len(full.splitlines())

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
        # At least one function should have a docstring
        has_docstring = False
        for mod in result["modules"]:
            for fn in mod.get("functions", []):
                if fn.get("docstring"):
                    has_docstring = True
        assert has_docstring

    def test_full_includes_imports(self):
        pkg = analyze_package(SAMPLE_PKG)
        result = format_json(pkg, detail="full")
        has_imports = any(len(mod.get("imports", [])) > 0 for mod in result["modules"])
        assert has_imports


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
