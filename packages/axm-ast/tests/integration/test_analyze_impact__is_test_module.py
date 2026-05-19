"""Drive ``_is_test_module`` (test-module classifier) through public ``analyze_impact``.

The private helper is the filter applied behind the ``exclude_tests`` /
``test_filter`` parameters of :func:`axm_ast.core.impact.analyze_impact`.
We assert its observable effect on the public result instead of importing it.
"""

import warnings
from pathlib import Path

from axm_ast.core.impact import analyze_impact
from tests.integration._helpers import (
    _make_project_with_test_callers,
    _make_project_with_test_callers__from_impact_test_filter,
)


def _is_test_module_name(module: str) -> bool:
    """Local mirror of the public classification rule for assertion purposes.

    A module is a test module when any dotted segment starts with ``test_``
    or equals ``tests`` (see ``analyze_impact`` filter docs).
    """
    parts = module.split(".")
    return any(p.startswith("test_") or p == "tests" for p in parts)


def test_exclude_tests_filters_test_callers(tmp_path: Path) -> None:
    """Only prod callers remain when exclude_tests=True."""
    pkg_dir = _make_project_with_test_callers(tmp_path)
    result = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=True
    )
    for caller in result["callers"]:
        assert not _is_test_module_name(caller["module"]), (
            f"Test caller not filtered: {caller['module']}"
        )
    # At least the cli caller should remain
    modules = [c["module"] for c in result["callers"]]
    assert any("cli" in m for m in modules)


def test_exclude_tests_false_keeps_all(tmp_path: Path) -> None:
    """Default (False) preserves all callers including tests."""
    pkg_dir = _make_project_with_test_callers(tmp_path)
    result = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=False
    )
    modules = [c["module"] for c in result["callers"]]
    # Should include test callers
    assert any(_is_test_module_name(m) for m in modules)


def test_exclude_tests_filters_type_refs(tmp_path: Path) -> None:
    """Type refs from test modules are filtered."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models."""\nclass MyModel:\n    """A model."""\n    pass\n'
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\ndef process(m: MyModel) -> None:\n    """Process."""\n    pass\n'
    )
    (pkg / "test_models.py").write_text(
        '"""Test models."""\n'
        "def check(m: MyModel) -> None:\n"
        '    """Check."""\n'
        "    pass\n"
    )
    result = analyze_impact(pkg, "MyModel", project_root=tmp_path, exclude_tests=True)
    for ref in result["type_refs"]:
        assert not _is_test_module_name(ref["module"]), (
            f"Test type ref not filtered: {ref['module']}"
        )


def test_impact_test_filter_none_excludes_tests(tmp_path: Path) -> None:
    """test_filter='none' removes all test callers from output."""
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(pkg, "target_fn", project_root=tmp_path, test_filter="none")
    # No callers from test modules
    for caller in result["callers"]:
        assert not _is_test_module_name(caller["module"]), (
            f"Test caller should be excluded: {caller['module']}"
        )
    # type_refs from test modules should also be excluded
    for ref in result.get("type_refs", []):
        assert not _is_test_module_name(ref["module"])


def test_impact_test_filter_all_includes_all(tmp_path: Path) -> None:
    """test_filter='all' keeps all callers including tests."""
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(pkg, "target_fn", project_root=tmp_path, test_filter="all")
    # Should have both prod and test callers
    modules = [c["module"] for c in result["callers"]]
    has_test = any(_is_test_module_name(m) for m in modules)
    has_prod = any(not _is_test_module_name(m) for m in modules)
    assert has_test, "test_filter='all' should include test callers"
    assert has_prod, "test_filter='all' should include prod callers"


def test_impact_test_filter_related_direct_only(tmp_path: Path) -> None:
    """test_filter='related' keeps only direct test callers.

    test_a calls target_fn directly -> included.
    test_b calls engine.run() (transitive) -> excluded.
    """
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(
        pkg, "target_fn", project_root=tmp_path, test_filter="related"
    )
    test_callers = [c for c in result["callers"] if _is_test_module_name(c["module"])]
    test_modules = {c["module"] for c in test_callers}
    # test_a calls target_fn directly -> included
    assert any("test_a" in m for m in test_modules), (
        "Direct test caller test_a should be included"
    )
    # test_b only calls engine.run -> excluded
    assert not any("test_b" in m for m in test_modules), (
        "Transitive test caller test_b should be excluded"
    )


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
        test_callers = [
            c for c in result["callers"] if _is_test_module_name(c["module"])
        ]
        test_modules = {c["module"] for c in test_callers}
        # Only direct test (test_models) should be included
        assert any("test_models" in m for m in test_modules)
        # Transitive tests should not appear
        for m in test_modules:
            assert "test_pipe" not in m

    def test_no_test_callers_related_returns_empty(self, tmp_path: Path) -> None:
        """Symbol with zero test references -> related returns empty test section."""
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
        test_callers = [
            c for c in result["callers"] if _is_test_module_name(c["module"])
        ]
        assert test_callers == [], "No test callers should be present"

    def test_both_params_test_filter_takes_precedence(self, tmp_path: Path) -> None:
        """test_filter takes precedence over exclude_tests, with a warning."""
        pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
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
                c for c in result["callers"] if _is_test_module_name(c["module"])
            ]
            assert len(test_callers) > 0, (
                "test_filter='all' should include test callers "
                "even when exclude_tests=True"
            )
            # Should emit a warning about conflicting params
            assert any("test_filter" in str(warning.message) for warning in w), (
                "Should warn about conflicting exclude_tests and test_filter"
            )
