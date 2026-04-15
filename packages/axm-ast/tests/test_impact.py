"""TDD tests for axm-ast impact — change impact analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import (
    _find_test_files_by_import,
    _is_test_module,
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
        '"""Pkg."""\nfrom .core import helper\n\n__all__ = ["helper"]\n'
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
        '"""Test core."""\ndef test_helper() -> None:\n    """Test."""\n    helper(1)\n'
    )
    (tests / "test_cli.py").write_text(
        '"""Test CLI."""\ndef test_main() -> None:\n    """Test."""\n    main()\n'
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
            '"""Pkg."""\nclass Engine:\n    """Engine."""\n    pass\n'
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
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
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


# ─── Import heuristic ───────────────────────────────────────────────────────


def _make_import_heuristic_project(tmp_path: Path) -> Path:
    """Create a project with an untested symbol whose module is imported."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Mypkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models module."""\n'
        "class InternalCfg:\n"
        '    """Internal configuration dataclass."""\n'
        '    name: str = "default"\n'
    )
    (pkg / "cli.py").write_text(
        '"""CLI module."""\ndef main() -> None:\n    """Main."""\n    pass\n'
    )
    # Tests directory: imports the models *module* but does NOT mention "InternalCfg"
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_models.py").write_text(
        '"""Test models."""\n'
        "import mypkg.models\n"
        "\n"
        "def test_something() -> None:\n"
        '    """Test."""\n'
        "    assert True\n"
    )
    # A non-test file that imports the module (should be excluded)
    (tmp_path / "helper_script.py").write_text(
        '"""Not a test."""\nimport mypkg.models\n'
    )
    return pkg


class TestImportHeuristic:
    """Test import-based test file heuristic in analyze_impact."""

    def test_import_heuristic_fires(self, tmp_path: Path) -> None:
        """Heuristic finds test files importing the symbol's module."""
        _make_import_heuristic_project(tmp_path)
        # UserConfig has no callers in the package, so map_tests won't find it by name
        # but test_models.py imports mypkg.models
        result = _find_test_files_by_import("models", tmp_path)
        names = [p.name for p in result]
        assert "test_models.py" in names

    def test_import_heuristic_skipped_in_analyze(self, tmp_path: Path) -> None:
        """When caller-based test_files is non-empty, heuristic does NOT run."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        # This test directly references "helper" → map_tests will find it
        (tests / "test_pkg.py").write_text(
            '"""Test."""\n'
            "from pkg import helper\n"
            "\n"
            "def test_helper() -> None:\n"
            '    """Test."""\n'
            "    helper()\n"
        )
        result = analyze_impact(pkg, "helper", project_root=tmp_path)
        assert "test_pkg.py" in result["test_files"]
        # Heuristic should not have run
        assert result.get("test_files_by_import") is None

    def test_import_heuristic_scoped_to_tests(self, tmp_path: Path) -> None:
        """Non-test files importing the module are not included."""
        _make_import_heuristic_project(tmp_path)
        result = _find_test_files_by_import("models", tmp_path)
        names = [p.name for p in result]
        # helper_script.py is at project root, not in tests/
        assert "helper_script.py" not in names

    def test_no_tests_import_module(self, tmp_path: Path) -> None:
        """Completely untested module returns empty."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "orphan.py").write_text(
            '"""Orphan module."""\ndef nobody() -> None:\n    pass\n'
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_other.py").write_text(
            '"""Test other."""\ndef test_x() -> None:\n    assert True\n'
        )
        result = _find_test_files_by_import("orphan", tmp_path)
        assert result == []

    def test_wildcard_import_detected(self, tmp_path: Path) -> None:
        """from module import * is still detected."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "utils.py").write_text(
            '"""Utils."""\ndef util_fn() -> None:\n    pass\n'
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_utils.py").write_text(
            '"""Test utils."""\nfrom mypkg.utils import *\n\n'
            "def test_u() -> None:\n    assert True\n"
        )
        result = _find_test_files_by_import("utils", tmp_path)
        names = [p.name for p in result]
        assert "test_utils.py" in names

    def test_full_analyze_impact_with_heuristic(self, tmp_path: Path) -> None:
        """Integration: analyze_impact returns test_files_by_import."""
        pkg = _make_import_heuristic_project(tmp_path)
        result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
        # InternalCfg has no callers in the package code
        assert result["callers"] == []
        # map_tests won't find it (name doesn't appear in test files)
        assert result["test_files"] == []
        # But the heuristic should find test_models.py via module import
        assert "test_files_by_import" in result
        assert "test_models.py" in result["test_files_by_import"]


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


# ─── Dotted symbol resolution ────────────────────────────────────────────────


def _make_dotted_project(tmp_path: Path) -> Path:
    """Create a project with classes, methods, properties, and nested classes."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models."""\n'
        "class Foo:\n"
        '    """Foo class."""\n'
        "\n"
        "    def bar(self, x: int) -> int:\n"
        '        """Bar method."""\n'
        "        return x + 1\n"
        "\n"
        "    @property\n"
        "    def my_prop(self) -> str:\n"
        '        """A property."""\n'
        '        return "hello"\n'
    )
    (pkg / "nested.py").write_text(
        '"""Nested classes."""\n'
        "class Outer:\n"
        '    """Outer class."""\n'
        "\n"
        "    class Inner:\n"
        '        """Inner class."""\n'
        "\n"
        "        def method(self) -> None:\n"
        '            """Inner method."""\n'
        "            pass\n"
    )
    (pkg / "use.py").write_text(
        '"""Usage module."""\n'
        "def call_bar() -> None:\n"
        '    """Call bar."""\n'
        "    f = Foo()\n"
        "    f.bar(42)\n"
    )
    return pkg


class TestDottedSymbol:
    """Tests for dotted symbol resolution (Class.method)."""

    def test_impact_dotted_method(self, tmp_path: Path) -> None:
        """Dotted method returns non-null definition with kind=method."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.bar", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] in ("method", "function")
        assert result["definition"]["line"] > 0

    def test_impact_dotted_callers(self, tmp_path: Path) -> None:
        """Dotted method finds callers that call instance.method()."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.bar", project_root=tmp_path)
        assert len(result["callers"]) >= 1

    def test_impact_class_still_works(self, tmp_path: Path) -> None:
        """Bare class name still works after dotted support."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] == "class"

    def test_impact_dotted_nonexistent(self, tmp_path: Path) -> None:
        """Non-existent method returns definition=None without crashing."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.nonexistent", project_root=tmp_path)
        assert result["definition"] is None

    def test_impact_dotted_property(self, tmp_path: Path) -> None:
        """Property is resolved like a method."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.my_prop", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] == "property"

    def test_impact_dotted_nested(self, tmp_path: Path) -> None:
        """Nested class method (Outer.Inner.method) — best-effort resolution."""
        pkg_dir = _make_dotted_project(tmp_path)
        # Should not crash; best-effort resolution
        result = analyze_impact(pkg_dir, "Outer.Inner.method", project_root=tmp_path)
        # We accept either a found definition or None — main thing is no crash
        assert isinstance(result, dict)
        assert "definition" in result

    def test_impact_on_real_symbol(self) -> None:
        """Dogfood on get_package (primary entry point after cache migration)."""
        root = Path(__file__).parent.parent
        ast_dir = root / "src" / "axm_ast"
        if ast_dir.exists():
            result = analyze_impact(ast_dir, "get_package", project_root=root)
            assert result["score"] in ("HIGH", "MEDIUM")
            assert len(result["callers"]) >= 1


# ─── exclude_tests ────────────────────────────────────────────────────────────


def _make_project_with_test_callers(tmp_path: Path) -> Path:
    """Create a project where a symbol is called from both prod and test code."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\ndef main() -> None:\n    """Main."""\n    helper(42)\n'
    )
    # Test callers — module names will start with "tests." or "test_"
    (pkg / "tests").mkdir()
    (pkg / "tests" / "__init__.py").write_text('"""Tests."""\n')
    (pkg / "tests" / "test_runner.py").write_text(
        '"""Test runner."""\n'
        "def test_helper() -> None:\n"
        '    """Test."""\n'
        "    helper(1)\n"
    )
    # Also a top-level test_ module
    (pkg / "test_smoke.py").write_text(
        '"""Smoke tests."""\ndef smoke() -> None:\n    """Smoke."""\n    helper(99)\n'
    )
    return pkg


class TestExcludeTests:
    """Tests for exclude_tests parameter."""

    def test_exclude_tests_filters_test_callers(self, tmp_path: Path) -> None:
        """Only prod callers remain when exclude_tests=True."""
        pkg_dir = _make_project_with_test_callers(tmp_path)
        result = analyze_impact(
            pkg_dir, "helper", project_root=tmp_path, exclude_tests=True
        )
        for caller in result["callers"]:
            assert not _is_test_module(caller["module"]), (
                f"Test caller not filtered: {caller['module']}"
            )
        # At least the cli caller should remain
        modules = [c["module"] for c in result["callers"]]
        assert any("cli" in m for m in modules)

    def test_exclude_tests_preserves_score(self, tmp_path: Path) -> None:
        """Score is computed on the FULL caller set before filtering."""
        pkg_dir = _make_project_with_test_callers(tmp_path)
        result_full = analyze_impact(
            pkg_dir, "helper", project_root=tmp_path, exclude_tests=False
        )
        result_filtered = analyze_impact(
            pkg_dir, "helper", project_root=tmp_path, exclude_tests=True
        )
        assert result_filtered["score"] == result_full["score"]

    def test_exclude_tests_false_keeps_all(self, tmp_path: Path) -> None:
        """Default (False) preserves all callers including tests."""
        pkg_dir = _make_project_with_test_callers(tmp_path)
        result = analyze_impact(
            pkg_dir, "helper", project_root=tmp_path, exclude_tests=False
        )
        modules = [c["module"] for c in result["callers"]]
        # Should include test callers
        assert any(_is_test_module(m) for m in modules)

    def test_exclude_tests_filters_type_refs(self, tmp_path: Path) -> None:
        """Type refs from test modules are filtered."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "models.py").write_text(
            '"""Models."""\nclass MyModel:\n    """A model."""\n    pass\n'
        )
        (pkg / "cli.py").write_text(
            '"""CLI."""\n'
            "def process(m: MyModel) -> None:\n"
            '    """Process."""\n'
            "    pass\n"
        )
        (pkg / "test_models.py").write_text(
            '"""Test models."""\n'
            "def check(m: MyModel) -> None:\n"
            '    """Check."""\n'
            "    pass\n"
        )
        result = analyze_impact(
            pkg, "MyModel", project_root=tmp_path, exclude_tests=True
        )
        for ref in result["type_refs"]:
            assert not _is_test_module(ref["module"]), (
                f"Test type ref not filtered: {ref['module']}"
            )

    def test_tool_passes_exclude_tests(self, tmp_path: Path) -> None:
        """ImpactTool.execute forwards exclude_tests to analyze_impact."""
        from unittest.mock import patch

        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        with patch("axm_ast.tools.impact.ImpactTool._analyze_single") as mock:
            mock.return_value = {"symbol": "foo", "score": "LOW", "definition": {}}
            tool.execute(path=str(tmp_path), symbol="foo", exclude_tests=True)
            mock.assert_called_once_with(tmp_path, "foo", exclude_tests=True)

    def test_all_callers_are_tests(self, tmp_path: Path) -> None:
        """Symbol only used in tests → empty callers, score still computed."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\ndef internal() -> None:\n    """Internal."""\n    pass\n'
        )
        (pkg / "test_core.py").write_text(
            '"""Test."""\ndef test_it() -> None:\n    """Test."""\n    internal()\n'
        )
        result_full = analyze_impact(
            pkg, "internal", project_root=tmp_path, exclude_tests=False
        )
        result_filtered = analyze_impact(
            pkg, "internal", project_root=tmp_path, exclude_tests=True
        )
        assert result_filtered["callers"] == []
        assert result_filtered["score"] == result_full["score"]

    def test_no_test_callers(self, tmp_path: Path) -> None:
        """No test callers → output identical with or without flag."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        (pkg / "cli.py").write_text(
            '"""CLI."""\ndef main() -> None:\n    """Main."""\n    helper()\n'
        )
        result_with = analyze_impact(
            pkg, "helper", project_root=tmp_path, exclude_tests=True
        )
        result_without = analyze_impact(
            pkg, "helper", project_root=tmp_path, exclude_tests=False
        )
        assert result_with["callers"] == result_without["callers"]


# ─── Cross-package blast radius ──────────────────────────────────────────────


def _make_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a workspace with two packages: pkg_a depends on pkg_b.

    Layout:
        workspace/
        ├── pkg_b/
        │   ├── __init__.py   (exports shared_model via __all__)
        │   └── models.py     (defines shared_model)
        └── pkg_a/
            ├── __init__.py
            └── consumer.py   (imports shared_model from pkg_b)

    Returns (workspace, pkg_a, pkg_b).
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # pkg_b — the provider
    pkg_b = workspace / "pkg_b"
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text(
        '"""Package B."""\nfrom .models import shared_model\n\n'
        '__all__ = ["shared_model"]\n'
    )
    (pkg_b / "models.py").write_text(
        '"""Models."""\n'
        "def shared_model(x: int) -> int:\n"
        '    """Shared model used across packages."""\n'
        "    return x * 2\n"
        "\n"
        "def _private_helper() -> None:\n"
        '    """Private — not in __all__."""\n'
        "    pass\n"
    )

    # pkg_a — the consumer
    pkg_a = workspace / "pkg_a"
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text('"""Package A."""\n')
    (pkg_a / "consumer.py").write_text(
        '"""Consumer."""\n'
        "from pkg_b import shared_model\n"
        "\n"
        "def process() -> int:\n"
        '    """Process using shared model."""\n'
        "    return shared_model(42)\n"
    )

    return workspace, pkg_a, pkg_b


class TestCrossPackageImpact:
    """Tests for cross-package blast radius detection (AXM-797)."""

    def test_cross_package_deps_detected(self, tmp_path: Path) -> None:
        """Symbol in __all__ imported by sibling → in cross_package_impact."""
        workspace, _pkg_a, pkg_b = _make_workspace(tmp_path)
        result = analyze_impact(pkg_b, "shared_model", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        # pkg_a imports shared_model from pkg_b → must appear
        assert any("pkg_a" in entry for entry in cross), (
            f"Expected pkg_a in cross_package_impact, got {cross}"
        )

    def test_no_cross_package_when_symbol_private(self, tmp_path: Path) -> None:
        """Private symbol (not in __all__) → cross_package_impact empty."""
        workspace, _pkg_a, pkg_b = _make_workspace(tmp_path)
        result = analyze_impact(pkg_b, "_private_helper", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        assert cross == [], (
            f"Private symbol should have no cross-package impact, got {cross}"
        )

    def test_circular_dependency_no_infinite_loop(self, tmp_path: Path) -> None:
        """Circular dep (pkg_a ↔ pkg_b) terminates without infinite loop."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # pkg_b imports from pkg_a
        pkg_b = workspace / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            '"""Package B."""\nfrom .core import func_b\n\n__all__ = ["func_b"]\n'
        )
        (pkg_b / "core.py").write_text(
            '"""Core B."""\n'
            "from pkg_a import func_a\n"
            "\n"
            "def func_b() -> int:\n"
            '    """B calls A."""\n'
            "    return func_a() + 1\n"
        )

        # pkg_a imports from pkg_b
        pkg_a = workspace / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            '"""Package A."""\nfrom .core import func_a\n\n__all__ = ["func_a"]\n'
        )
        (pkg_a / "core.py").write_text(
            '"""Core A."""\n'
            "from pkg_b import func_b\n"
            "\n"
            "def func_a() -> int:\n"
            '    """A calls B."""\n'
            "    return func_b() + 1\n"
        )

        result = analyze_impact(pkg_b, "func_b", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        # Both packages should appear (mutual dependency), no hang
        assert any("pkg_a" in entry for entry in cross), (
            f"Expected pkg_a in circular cross-package impact, got {cross}"
        )

    def test_symbol_not_imported_excluded(self, tmp_path: Path) -> None:
        """pkg_a depends on pkg_b but doesn't import the changed symbol → not listed."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        pkg_b = workspace / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            '"""Package B."""\n'
            "from .models import used_func, unused_func\n\n"
            '__all__ = ["used_func", "unused_func"]\n'
        )
        (pkg_b / "models.py").write_text(
            '"""Models."""\n'
            "def used_func() -> int:\n"
            '    """Used by pkg_a."""\n'
            "    return 1\n"
            "\n"
            "def unused_func() -> int:\n"
            '    """Not imported by pkg_a."""\n'
            "    return 2\n"
        )

        pkg_a = workspace / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text('"""Package A."""\n')
        (pkg_a / "consumer.py").write_text(
            '"""Consumer."""\n'
            "from pkg_b import used_func\n"
            "\n"
            "def run() -> int:\n"
            '    """Only uses used_func."""\n'
            "    return used_func()\n"
        )

        result = analyze_impact(pkg_b, "unused_func", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        assert not any("pkg_a" in entry for entry in cross), (
            f"pkg_a should NOT appear for unused_func, got {cross}"
        )
