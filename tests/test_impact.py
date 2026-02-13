"""TDD tests for axm-ast impact — change impact analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import (
    analyze_impact,
    find_definition,
    find_reexports,
    map_tests,
    score_impact,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_project(tmp_path: Path) -> Path:
    """Create a typical project with init, module, and tests."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\n' "from .core import helper\n" "\n" '__all__ = ["helper"]\n'
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
        "\n"
        "def _private() -> None:\n"
        '    """Private."""\n'
        "    pass\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\n'
        "def main() -> None:\n"
        '    """Main."""\n'
        "    helper(42)\n"
        "\n"
        "def other() -> None:\n"
        '    """Other."""\n'
        "    helper(99)\n"
    )
    # Tests directory
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        '"""Test core."""\n'
        "def test_helper() -> None:\n"
        '    """Test."""\n'
        "    helper(1)\n"
    )
    (tests / "test_cli.py").write_text(
        '"""Test CLI."""\n'
        "def test_main() -> None:\n"
        '    """Test."""\n'
        "    main()\n"
    )
    return pkg


# ─── Unit: find_definition ───────────────────────────────────────────────────


class TestFindDefinition:
    """Test symbol definition location."""

    def test_find_function(self, tmp_path: Path) -> None:
        """Finds function in correct module with line."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        defn = find_definition(pkg, "helper")
        assert defn is not None
        assert "core" in defn["module"]
        assert defn["line"] > 0

    def test_find_class(self, tmp_path: Path) -> None:
        """Finds class definition."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\n' "class Engine:\n" '    """Engine."""\n' "    pass\n"
        )
        info = analyze_package(pkg)
        defn = find_definition(info, "Engine")
        assert defn is not None
        assert defn["kind"] == "class"

    def test_not_found(self, tmp_path: Path) -> None:
        """Unknown symbol returns None."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        defn = find_definition(pkg, "nonexistent")
        assert defn is None


# ─── Unit: find_reexports ────────────────────────────────────────────────────


class TestFindReexports:
    """Test re-export detection."""

    def test_reexport_in_init(self, tmp_path: Path) -> None:
        """Detects re-export in __init__.py via __all__."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        reexports = find_reexports(pkg, "helper")
        assert len(reexports) >= 1
        assert any("__init__" in r or r.endswith("pkg") for r in reexports)

    def test_no_reexport(self, tmp_path: Path) -> None:
        """Symbol not re-exported returns empty."""
        pkg_dir = _make_project(tmp_path)
        pkg = analyze_package(pkg_dir)
        reexports = find_reexports(pkg, "_private")
        assert reexports == []


# ─── Unit: map_tests ────────────────────────────────────────────────────────


class TestMapTests:
    """Test test file detection."""

    def test_finds_relevant_tests(self, tmp_path: Path) -> None:
        """Identifies test files that reference the symbol."""
        _make_project(tmp_path)
        test_files = map_tests("helper", tmp_path)
        names = [t.name for t in test_files]
        assert "test_core.py" in names

    def test_no_tests_dir(self, tmp_path: Path) -> None:
        """Graceful when no tests/ exists."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        test_files = map_tests("helper", tmp_path)
        assert test_files == []


# ─── Unit: score_impact ─────────────────────────────────────────────────────


class TestScoreImpact:
    """Test impact scoring."""

    def test_high_impact(self) -> None:
        """Many callers + re-exported = HIGH."""
        result = {
            "callers": [1, 2, 3, 4, 5],
            "reexports": ["__init__"],
            "affected_modules": ["a", "b", "c"],
        }
        assert score_impact(result) == "HIGH"

    def test_low_impact(self) -> None:
        """No callers, no re-exports = LOW."""
        result: dict[str, list[str | int]] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
        }
        assert score_impact(result) == "LOW"

    def test_medium_impact(self) -> None:
        """Some callers = MEDIUM."""
        result = {
            "callers": [1, 2],
            "reexports": [],
            "affected_modules": ["a"],
        }
        assert score_impact(result) == "MEDIUM"


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestImpactEdgeCases:
    """Edge cases for impact analysis."""

    def test_symbol_no_callers(self, tmp_path: Path) -> None:
        """Defined but never called → LOW."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\n' "def lonely() -> None:\n" '    """Lonely."""\n' "    pass\n"
        )
        result = analyze_impact(pkg, "lonely", project_root=tmp_path)
        assert result["score"] == "LOW"
        assert result["callers"] == []

    def test_private_symbol(self, tmp_path: Path) -> None:
        """Private symbol impact analysis works."""
        pkg_dir = _make_project(tmp_path)
        result = analyze_impact(pkg_dir, "_private", project_root=tmp_path)
        assert result["score"] == "LOW"

    def test_method_impact(self, tmp_path: Path) -> None:
        """Method name impact detection."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\n'
            "class Calc:\n"
            '    """Calc."""\n'
            "    def add(self, x: int) -> int:\n"
            '        """Add."""\n'
            "        return x\n"
        )
        (pkg / "use.py").write_text(
            '"""Use."""\n'
            "def go() -> None:\n"
            '    """Go."""\n'
            "    c = Calc()\n"
            "    c.add(1)\n"
        )
        result = analyze_impact(pkg, "add", project_root=tmp_path)
        assert len(result["callers"]) >= 1


# ─── Functional: CLI ────────────────────────────────────────────────────────


class TestImpactCLI:
    """Test impact CLI command."""

    def test_impact_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI produces all sections."""
        from axm_ast.cli import app

        pkg_dir = _make_project(tmp_path)
        with pytest.raises(SystemExit):
            app(["impact", str(pkg_dir), "--symbol", "helper"])
        captured = capsys.readouterr()
        assert "helper" in captured.out
        assert "caller" in captured.out.lower() or "impact" in captured.out.lower()

    def test_impact_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output has all expected fields."""
        import json

        from axm_ast.cli import app

        pkg_dir = _make_project(tmp_path)
        with pytest.raises(SystemExit):
            app(["impact", str(pkg_dir), "--symbol", "helper", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "symbol" in data
        assert "callers" in data
        assert "score" in data

    def test_impact_on_real_symbol(self) -> None:
        """Dogfood on analyze_package."""
        root = Path(__file__).parent.parent
        ast_dir = root / "src" / "axm_ast"
        if ast_dir.exists():
            result = analyze_impact(ast_dir, "analyze_package", project_root=root)
            assert result["score"] == "HIGH"
            assert len(result["callers"]) >= 3
