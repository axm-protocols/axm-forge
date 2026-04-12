"""TDD tests for test_filter param on ast_impact (AXM-957).

Tests cover:
- Unit: test_filter="none"|"all"|"related" on analyze_impact
- Functional: compact format with test callers, MCP tool param
- Edge cases: fundamental type, no test callers, both params set
"""

from __future__ import annotations

import warnings
from pathlib import Path

from axm_ast.core.impact import _is_test_module, analyze_impact

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_project_with_test_callers(tmp_path: Path) -> Path:
    """Create a project where a symbol is called by both prod and test modules.

    Test files live **inside** the package so ``find_callers`` picks them up.

    Layout:
        pkg/
            __init__.py
            core.py        → def target_fn(x): ...
            engine.py      → calls target_fn (prod caller)
            test_a.py      → calls target_fn directly (direct test caller)
            tests/
                __init__.py
                test_b.py  → calls engine.run() (transitive only)
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\n'
        "def target_fn(x: int) -> int:\n"
        '    """Target function."""\n'
        "    return x + 1\n"
    )
    (pkg / "engine.py").write_text(
        '"""Engine."""\n'
        "def run() -> int:\n"
        '    """Run engine."""\n'
        "    return target_fn(42)\n"
    )
    # test_a: calls target_fn directly — top-level test module in package
    (pkg / "test_a.py").write_text(
        '"""Direct test."""\n'
        "def test_target_direct() -> None:\n"
        '    """Test."""\n'
        "    target_fn(1)\n"
    )
    # test_b: calls engine.run() only (transitive reference to target_fn)
    tests = pkg / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text('"""Tests."""\n')
    (tests / "test_b.py").write_text(
        '"""Transitive test."""\n'
        "def test_via_engine() -> None:\n"
        '    """Test."""\n'
        "    run()\n"
    )
    return pkg


# ─── Unit: test_filter on analyze_impact ─────────────────────────────────────


class TestImpactTestFilter:
    """Unit tests for the test_filter parameter."""

    def test_impact_test_filter_none_excludes_tests(self, tmp_path: Path) -> None:
        """test_filter='none' removes all test callers from output."""
        pkg = _make_project_with_test_callers(tmp_path)
        result = analyze_impact(
            pkg, "target_fn", project_root=tmp_path, test_filter="none"
        )
        # No callers from test modules
        for caller in result["callers"]:
            assert not _is_test_module(caller["module"]), (
                f"Test caller should be excluded: {caller['module']}"
            )
        # type_refs from test modules should also be excluded
        for ref in result.get("type_refs", []):
            assert not _is_test_module(ref["module"])

    def test_impact_test_filter_all_includes_all(self, tmp_path: Path) -> None:
        """test_filter='all' keeps all callers including tests."""
        pkg = _make_project_with_test_callers(tmp_path)
        result = analyze_impact(
            pkg, "target_fn", project_root=tmp_path, test_filter="all"
        )
        # Should have both prod and test callers
        modules = [c["module"] for c in result["callers"]]
        has_test = any(_is_test_module(m) for m in modules)
        has_prod = any(not _is_test_module(m) for m in modules)
        assert has_test, "test_filter='all' should include test callers"
        assert has_prod, "test_filter='all' should include prod callers"

    def test_impact_test_filter_related_direct_only(self, tmp_path: Path) -> None:
        """test_filter='related' keeps only direct test callers.

        test_a calls target_fn directly → included.
        test_b calls engine.run() (transitive) → excluded.
        """
        pkg = _make_project_with_test_callers(tmp_path)
        result = analyze_impact(
            pkg, "target_fn", project_root=tmp_path, test_filter="related"
        )
        test_callers = [c for c in result["callers"] if _is_test_module(c["module"])]
        test_modules = {c["module"] for c in test_callers}
        # test_a calls target_fn directly → included
        assert any("test_a" in m for m in test_modules), (
            "Direct test caller test_a should be included"
        )
        # test_b only calls engine.run → excluded
        assert not any("test_b" in m for m in test_modules), (
            "Transitive test caller test_b should be excluded"
        )

    def test_impact_exclude_tests_backward_compat(self, tmp_path: Path) -> None:
        """exclude_tests=True produces same result as test_filter='none'."""
        pkg = _make_project_with_test_callers(tmp_path)
        result_legacy = analyze_impact(
            pkg, "target_fn", project_root=tmp_path, exclude_tests=True
        )
        result_new = analyze_impact(
            pkg, "target_fn", project_root=tmp_path, test_filter="none"
        )
        assert result_legacy["callers"] == result_new["callers"]
        assert result_legacy.get("type_refs", []) == result_new.get("type_refs", [])


# ─── Functional: compact format + MCP tool ──────────────────────────────────


class TestImpactTestFilterFunctional:
    """Functional tests for test_filter integration."""

    def test_impact_compact_with_test_callers(self, tmp_path: Path) -> None:
        """Compact output includes test caller lines when test_filter='related'."""
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_project_with_test_callers(tmp_path)
        tool = ImpactTool()
        result = tool.execute(
            path=str(pkg),
            symbol="target_fn",
            test_filter="related",
            detail="compact",
        )
        assert result.success
        compact = result.text
        # Compact output should contain the test caller reference
        assert compact is not None
        assert "test_a" in compact

    def test_impact_mcp_test_filter_param(self, tmp_path: Path) -> None:
        """MCP tool accepts test_filter param and returns filtered results."""
        from axm_ast.tools.impact import ImpactTool

        pkg = _make_project_with_test_callers(tmp_path)
        tool = ImpactTool()
        result = tool.execute(
            path=str(pkg),
            symbol="target_fn",
            test_filter="related",
        )
        assert result.success
        test_callers = [
            c for c in result.data["callers"] if _is_test_module(c["module"])
        ]
        test_modules = {c["module"] for c in test_callers}
        assert any("test_a" in m for m in test_modules)
        assert not any("test_b" in m for m in test_modules)


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestImpactTestFilterEdgeCases:
    """Edge cases for test_filter parameter."""

    def test_fundamental_type_related_filters_transitive(self, tmp_path: Path) -> None:
        """Symbol used in many tests but directly tested by few.

        FlowStep-like scenario: imported as a type in many test files
        but only directly exercised in a few.
        """
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "models.py").write_text(
            '"""Models."""\n'
            "class FlowStep:\n"
            '    """A flow step."""\n'
            "    def run(self) -> str:\n"
            '        """Run."""\n'
            '        return "ok"\n'
        )
        (pkg / "pipeline.py").write_text(
            '"""Pipeline."""\n'
            "def execute_pipeline() -> str:\n"
            '    """Execute."""\n'
            "    return FlowStep().run()\n"
        )
        # Direct test: exercises FlowStep directly (inside package)
        (pkg / "test_models.py").write_text(
            '"""Direct test of FlowStep."""\n'
            "def test_flowstep_run() -> None:\n"
            '    """Test."""\n'
            "    FlowStep()\n"
        )
        # Transitive tests: call pipeline, not FlowStep (inside package)
        tests = pkg / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text('"""Tests."""\n')
        for i in range(3):
            (tests / f"test_pipe_{i}.py").write_text(
                f'"""Pipeline test {i}."""\n'
                f"def test_pipeline_{i}() -> None:\n"
                '    """Test."""\n'
                "    execute_pipeline()\n"
            )

        result = analyze_impact(
            pkg, "FlowStep", project_root=tmp_path, test_filter="related"
        )
        test_callers = [c for c in result["callers"] if _is_test_module(c["module"])]
        test_modules = {c["module"] for c in test_callers}
        # Only direct test (test_models) should be included
        assert any("test_models" in m for m in test_modules)
        # Transitive tests should not appear
        for m in test_modules:
            assert "test_pipe" not in m

    def test_no_test_callers_related_returns_empty(self, tmp_path: Path) -> None:
        """Symbol with zero test references → related returns empty test section."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\n'
            "def internal_fn() -> int:\n"
            '    """No tests reference this."""\n'
            "    return 42\n"
        )
        (pkg / "api.py").write_text(
            '"""API."""\n'
            "def handler() -> int:\n"
            '    """Handler."""\n'
            "    return internal_fn()\n"
        )

        result = analyze_impact(
            pkg, "internal_fn", project_root=tmp_path, test_filter="related"
        )
        test_callers = [c for c in result["callers"] if _is_test_module(c["module"])]
        assert test_callers == [], "No test callers should be present"

    def test_both_params_test_filter_takes_precedence(self, tmp_path: Path) -> None:
        """test_filter takes precedence over exclude_tests, with a warning."""
        pkg = _make_project_with_test_callers(tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = analyze_impact(
                pkg,
                "target_fn",
                project_root=tmp_path,
                exclude_tests=True,
                test_filter="all",
            )
            # test_filter="all" should win: test callers included
            test_callers = [
                c for c in result["callers"] if _is_test_module(c["module"])
            ]
            assert len(test_callers) > 0, (
                "test_filter='all' should include test callers "
                "even when exclude_tests=True"
            )
            # Should emit a warning about conflicting params
            assert any("test_filter" in str(warning.message) for warning in w), (
                "Should warn about conflicting exclude_tests and test_filter"
            )
