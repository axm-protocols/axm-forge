from __future__ import annotations

from typing import Any

import pytest

from axm_ast.tools.impact import (
    _render_impact_single,
    render_impact_batch_text,
    render_impact_text,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def full_report() -> dict[str, Any]:
    """Report dict with all fields populated."""
    return {
        "symbol": "my_func",
        "score": "HIGH",
        "definition": {
            "kind": "function",
            "module": "pkg.mod",
            "line": 42,
            "signature": "def my_func(x: int) -> str",
        },
        "callers": [
            {"name": "caller_a", "module": "pkg.caller", "line": 10},
            {"name": "caller_b", "module": "pkg.other", "line": 20},
        ],
        "affected_modules": ["pkg.mod", "pkg.caller"],
        "test_files": ["tests/test_mod.py", "tests/sub/test_other.py"],
        "git_coupled": ["src/pkg/helper.py", "src/pkg/util.py"],
        "cross_package_impact": [
            {"package": "other-pkg", "module": "other_pkg.api"},
            "plain_string_entry",
        ],
    }


@pytest.fixture
def minimal_report() -> dict[str, Any]:
    """Report dict with only symbol + score."""
    return {"symbol": "bare_sym", "score": "LOW"}


@pytest.fixture
def error_report() -> dict[str, Any]:
    """Report dict with an error key."""
    return {"symbol": "broken", "error": "could not resolve symbol"}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestRenderImpactSingleFull:
    """test_render_impact_single_full: all fields populated."""

    def test_header_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        lines = result.split("\n")
        assert lines[0] == "ast_impact | my_func | HIGH"

    def test_definition_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Def: pkg.mod:42 (function)" in result

    def test_signature_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "def my_func(x: int) -> str" in result

    def test_callers_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Callers: caller_a (pkg.caller:10), caller_b (pkg.other:20)" in result

    def test_affected_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Affected: pkg.mod, pkg.caller" in result

    def test_tests_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Tests: test_mod.py, test_other.py" in result

    def test_git_coupled_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Git-coupled: helper.py, util.py" in result

    def test_cross_package_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Cross-package: other-pkg, plain_string_entry" in result

    def test_full_output_matches(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        expected = (
            "ast_impact | my_func | HIGH\n"
            "Def: pkg.mod:42 (function)\n"
            "def my_func(x: int) -> str\n"
            "Callers: caller_a (pkg.caller:10), caller_b (pkg.other:20)\n"
            "Affected: pkg.mod, pkg.caller\n"
            "Tests: test_mod.py, test_other.py\n"
            "Git-coupled: helper.py, util.py\n"
            "Cross-package: other-pkg, plain_string_entry"
        )
        assert result == expected


class TestRenderImpactSingleMinimal:
    """test_render_impact_single_minimal: only symbol + score."""

    def test_header_line(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        lines = result.split("\n")
        assert lines[0] == "ast_impact | bare_sym | LOW"

    def test_callers_none(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Callers: none" in result

    def test_tests_none(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Tests: none" in result

    def test_no_def_line(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Def:" not in result

    def test_no_affected(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Affected:" not in result

    def test_no_git_coupled(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Git-coupled:" not in result

    def test_no_cross_package(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Cross-package:" not in result


class TestRenderImpactSingleError:
    """test_render_impact_single_error: report with error key."""

    def test_error_output(self, error_report: dict[str, Any]) -> None:
        result = _render_impact_single(error_report)
        assert result == "ast_impact | broken | error\ncould not resolve symbol"

    def test_error_no_extra_sections(self, error_report: dict[str, Any]) -> None:
        result = _render_impact_single(error_report)
        assert "Callers:" not in result
        assert "Tests:" not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestRenderImpactEdgeCases:
    def test_empty_callers_list(self) -> None:
        """Empty callers list -> 'Callers: none'."""
        report: dict[str, Any] = {"symbol": "s", "score": "LOW", "callers": []}
        result = _render_impact_single(report)
        assert "Callers: none" in result

    def test_cross_package_mixed_types(self) -> None:
        """Cross-package with both dict and str entries."""
        report: dict[str, Any] = {
            "symbol": "s",
            "score": "LOW",
            "cross_package_impact": [
                {"package": "pkg-a"},
                "raw-string",
                {"module": "fallback.mod"},
            ],
        }
        result = _render_impact_single(report)
        assert "Cross-package: pkg-a, raw-string, fallback.mod" in result

    def test_missing_definition(self) -> None:
        """No 'defn' key -> no 'Def:' line."""
        report: dict[str, Any] = {"symbol": "s", "score": "LOW"}
        result = _render_impact_single(report)
        assert "Def:" not in result

    def test_caller_without_line(self) -> None:
        """Caller entry missing line falls back to module only."""
        report: dict[str, Any] = {
            "symbol": "s",
            "score": "LOW",
            "callers": [{"name": "c", "module": "m"}],
        }
        result = _render_impact_single(report)
        assert "Callers: c (m)" in result


# ---------------------------------------------------------------------------
# Functional: render_impact_text / render_impact_batch_text
# ---------------------------------------------------------------------------


class TestRenderImpactText:
    def test_delegates_to_single(self, full_report: dict[str, Any]) -> None:
        assert render_impact_text(full_report) == _render_impact_single(full_report)

    def test_error_report(self, error_report: dict[str, Any]) -> None:
        assert render_impact_text(error_report) == _render_impact_single(error_report)


class TestRenderImpactBatchText:
    def test_empty_list(self) -> None:
        assert render_impact_batch_text([]) == ""

    def test_batch_header_max_score(
        self, full_report: dict[str, Any], minimal_report: dict[str, Any]
    ) -> None:
        result = render_impact_batch_text([full_report, minimal_report])
        assert result.startswith("ast_impact | 2 symbols | max=HIGH")

    def test_batch_contains_all_symbols(
        self, full_report: dict[str, Any], minimal_report: dict[str, Any]
    ) -> None:
        result = render_impact_batch_text([full_report, minimal_report])
        assert "## my_func | HIGH" in result
        assert "## bare_sym | LOW" in result
