"""Unit tests for axm_audit.core.rules.architecture.coupling."""

from __future__ import annotations

import ast
from typing import Any

import pytest

from axm_audit.core.rules.architecture.coupling import (
    build_coupling_result,
    extract_imports,
    parse_overrides,
    safe_int,
)
from axm_audit.models.results import AuditResult, CheckResult
from tests.unit._helpers import _RULE_CATEGORY

_EXPECTED_PUBLIC_SYMBOLS = (
    "tarjan_scc",
    "classify_module_role",
    "build_coupling_result",
    "extract_imports",
    "read_coupling_config",
    "strip_prefix",
    "parse_overrides",
    "safe_int",
)


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Helper to create a CheckResult with a score and category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=_RULE_CATEGORY.get(rule_id),
    )


def _build_severity_result(
    modules: dict[str, int],
    threshold: int = 10,
    severity_error_multiplier: int = 2,
) -> dict[str, Any]:
    """Shortcut to call build_coupling_result with simple fan-out dict."""
    fan_in = dict.fromkeys(modules, 1)
    return build_coupling_result(
        fan_out=modules,
        fan_in=fan_in,
        threshold=threshold,
        severity_error_multiplier=severity_error_multiplier,
    )


# ---------------------------------------------------------------------------
# build_coupling_result
# ---------------------------------------------------------------------------


class TestBuildCouplingResultUnit:
    def test_build_coupling_result_with_overrides(self) -> None:
        fan_out = {"mod_a": 11, "mod_b": 11}
        fan_in = {"mod_a": 2, "mod_b": 3}
        overrides = {"mod_a": 15}
        threshold = 10

        result = build_coupling_result(fan_out, fan_in, threshold, overrides)

        over_names = [entry["module"] for entry in result["over_threshold"]]
        assert "mod_b" in over_names
        assert "mod_a" not in over_names
        assert result["n_over_threshold"] == 1


# ---------------------------------------------------------------------------
# Helpers: safe_int / parse_overrides
# ---------------------------------------------------------------------------


class TestCouplingHelpersUnit:
    @pytest.mark.parametrize(
        ("value", "default", "expected"),
        [
            pytest.param(10, 5, 10, id="valid_positive"),
            pytest.param(0, 5, 0, id="valid_zero"),
            pytest.param("abc", 5, 5, id="non_int_falls_back"),
            pytest.param(-3, 5, 5, id="negative_falls_back"),
        ],
    )
    def test_safe_int(self, value: object, default: int, expected: int) -> None:
        assert safe_int(value, default) == expected

    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            pytest.param({"mod": 15}, {"mod": 15}, id="valid_dict"),
            pytest.param({"mod": "abc"}, {}, id="invalid_value"),
            pytest.param("invalid", {}, id="not_a_dict"),
        ],
    )
    def test_parse_overrides(
        self, input_value: object, expected: dict[str, int]
    ) -> None:
        assert parse_overrides(input_value) == expected


# ---------------------------------------------------------------------------
# Public API surface (AC1: helpers extracted as public symbols)
# ---------------------------------------------------------------------------


class TestCouplingPublicAPI:
    @pytest.mark.parametrize("name", _EXPECTED_PUBLIC_SYMBOLS)
    def test_coupling_module_exports(self, name: str) -> None:
        """Each promoted helper is importable from coupling submodule."""
        from axm_audit.core.rules.architecture import coupling

        assert hasattr(coupling, name), f"missing public symbol: {name}"
        assert callable(getattr(coupling, name))

    def test_coupling_private_aliases_removed(self) -> None:
        """Old underscore-prefixed names must not survive on the new module."""
        from axm_audit.core.rules.architecture import coupling

        for name in _EXPECTED_PUBLIC_SYMBOLS:
            assert not hasattr(coupling, f"_{name}"), (
                f"deprecated alias _{name} still exposed on coupling module"
            )


# ---------------------------------------------------------------------------
# extract_imports: count modules, not symbols
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for extract_imports counting modules not symbols."""

    def test_from_import_counts_module_not_symbols(self) -> None:
        """'from foo import A, B, C' = 1 import, not 4."""
        code = "from axm_init.models import CheckResult, Severity, Config"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert len(imports) == 1
        assert imports[0] == "axm_init.models"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param("import os", ["os"], id="plain_import"),
            pytest.param("from . import x", [], id="relative_import_no_module"),
        ],
    )
    def test_single_statement(self, code: str, expected: list[str]) -> None:
        """Single import statement produces the expected module list."""
        imports = extract_imports(ast.parse(code))
        assert imports == expected

    def test_multiple_imports(self) -> None:
        """Multiple distinct import statements are counted separately."""
        code = "import os\nimport sys\nfrom pathlib import Path"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert set(imports) == {"os", "sys", "pathlib"}

    def test_future_import_excluded(self) -> None:
        """'from __future__ import annotations' is a directive, not a dependency."""
        code = "from __future__ import annotations\nimport os\nfrom pathlib import Path"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert "__future__" not in imports
        assert set(imports) == {"os", "pathlib"}

    def test_future_import_only(self) -> None:
        """Module with only __future__ import has 0 fan-out."""
        imports = extract_imports(ast.parse("from __future__ import annotations"))
        assert imports == []


# ---------------------------------------------------------------------------
# Scoring integration: rule_id → category routing
# ---------------------------------------------------------------------------


class TestScoringIntegration:
    """End-to-end checks that registered rule IDs route to scored categories."""

    def test_perfect_scores_yield_100(self) -> None:
        """Every scored category at 100 → composite is 100."""
        checks = [
            _make_check("QUALITY_LINT", 100),
            _make_check("QUALITY_TYPE", 100),
            _make_check("QUALITY_COMPLEXITY", 100),
            _make_check("QUALITY_SECURITY", 100),
            _make_check("DEPS_AUDIT", 100),
            _make_check("QUALITY_COVERAGE", 100),
            _make_check("ARCH_COUPLING", 100),
            _make_check("PRACTICE_DOCSTRING", 100),
        ]
        result = AuditResult(checks=checks)
        assert result.quality_score == pytest.approx(100.0, abs=0.1)

    @pytest.mark.parametrize(
        "rule_id",
        [
            pytest.param("ARCH_COUPLING", id="architecture"),
            pytest.param("PRACTICE_DOCSTRING", id="practices"),
        ],
    )
    def test_rule_failure_lowers_composite(self, rule_id: str) -> None:
        """A rule dropping from 100 to 0 must lower the composite score."""
        baseline = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check(rule_id, 100),
            ]
        )
        degraded = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check(rule_id, 0),
            ]
        )
        assert baseline.quality_score is not None
        assert degraded.quality_score is not None
        assert degraded.quality_score < baseline.quality_score

    def test_practice_security_routes_to_security_category(self) -> None:
        """PRACTICE_SECURITY is registered under 'security' (not 'practices')."""
        assert _RULE_CATEGORY.get("PRACTICE_SECURITY") == "security"


# ---------------------------------------------------------------------------
# Tiered severity (AXM-1293)
# ---------------------------------------------------------------------------


class TestSeverityTiers:
    """Unit-scope tests for severity tiering (no real I/O)."""

    @pytest.mark.parametrize(
        ("fan_out", "expected_severity"),
        [
            pytest.param(12, "warning", id="borderline_above_threshold"),
            pytest.param(20, "warning", id="exact_error_boundary"),
            pytest.param(21, "error", id="just_past_error_boundary"),
            pytest.param(25, "error", id="extreme"),
        ],
    )
    def test_severity_tier_by_fan_out(
        self, fan_out: int, expected_severity: str
    ) -> None:
        """Severity tier (warning vs error) depends on fan-out vs threshold*mult."""
        result = _build_severity_result(
            {"mod_a": fan_out}, threshold=10, severity_error_multiplier=2
        )

        assert result["n_over_threshold"] == 1
        assert result["over_threshold"][0]["severity"] == expected_severity

    def test_multiplier_1_all_error(self) -> None:
        """multiplier=1 → all over-threshold modules are immediately ERROR."""
        result = _build_severity_result(
            {"mod_a": 11, "mod_b": 15},
            threshold=10,
            severity_error_multiplier=1,
        )

        assert result["n_over_threshold"] == 2
        for entry in result["over_threshold"]:
            assert entry["severity"] == "error"

    def test_mixed_severities(self) -> None:
        """Module A at warning, Module B at error → worst severity, passed=False."""
        result = _build_severity_result(
            {"mod_a": 12, "mod_b": 25, "mod_c": 5},
            threshold=10,
            severity_error_multiplier=2,
        )

        over = result["over_threshold"]
        assert len(over) == 2

        severities = {e["module"]: e["severity"] for e in over}
        assert severities["mod_a"] == "warning"
        assert severities["mod_b"] == "error"

    def test_scoring_differentiation(self) -> None:
        """2 warning + 1 error modules → score = 100 - (2x3 + 1x5) = 89."""
        result = _build_severity_result(
            {"mod_a": 12, "mod_b": 15, "mod_c": 25, "mod_d": 5},
            threshold=10,
            severity_error_multiplier=2,
        )

        over = result["over_threshold"]
        warnings = [e for e in over if e["severity"] == "warning"]
        errors = [e for e in over if e["severity"] == "error"]
        assert len(warnings) == 2
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Merged from tests/unit/core/rules/test_architecture.py
# ---------------------------------------------------------------------------


class TestCircularImportRuleUnit:
    """Pure tests for CircularImportRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_CIRCULAR."""
        from axm_audit.core.rules.architecture import CircularImportRule

        rule = CircularImportRule()
        assert rule.rule_id == "ARCH_CIRCULAR"


class TestGodClassRuleUnit:
    """Pure tests for GodClassRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_GOD_CLASS."""
        from axm_audit.core.rules.architecture import GodClassRule

        rule = GodClassRule()
        assert rule.rule_id == "ARCH_GOD_CLASS"


class TestCouplingMetricRuleUnit:
    """Pure tests for CouplingMetricRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_COUPLING."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        assert rule.rule_id == "ARCH_COUPLING"


class TestStripPrefix:
    """Tests for strip_prefix helper."""

    @pytest.mark.parametrize(
        ("modules", "expected"),
        [
            pytest.param(
                ["pkg.core.a", "pkg.core.b", "pkg.models.c"],
                ["core.a", "core.b", "models.c"],
                id="strips_shared_prefix",
            ),
            pytest.param(["a", "b"], ["a", "b"], id="no_dot_returns_unchanged"),
            pytest.param(
                ["pkg_a.mod", "pkg_b.mod"],
                ["pkg_a.mod", "pkg_b.mod"],
                id="mixed_prefix_returns_unchanged",
            ),
        ],
    )
    def test_strip_prefix(self, modules: list[str], expected: list[str]) -> None:
        """strip_prefix removes a shared top-level package only when present."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        assert strip_prefix(modules) == expected

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty."""
        from axm_audit.core.rules.architecture.coupling import strip_prefix

        assert strip_prefix([]) == []


class TestTarjanSCC:
    """Direct tests for the iterative tarjan_scc algorithm."""

    def test_tarjan_iterative_simple_cycle(self) -> None:
        """A->B->A graph detects SCC [A, B]."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {"A": {"B"}, "B": {"A"}}
        sccs = tarjan_scc(graph)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B"}

    @pytest.mark.parametrize(
        ("graph", "expected"),
        [
            pytest.param(
                {"A": {"B"}, "B": {"C"}, "C": set()},
                [],
                id="linear_chain_no_cycle",
            ),
            pytest.param(
                {f"n{i}": {f"n{i + 1}"} if i < 1999 else set() for i in range(2000)},
                [],
                id="deep_chain_no_recursion_error",
            ),
            pytest.param({"A": {"A"}}, [], id="self_loop_filtered"),
            pytest.param(
                {"A": set(), "B": set(), "C": set()}, [], id="disconnected_nodes"
            ),
        ],
    )
    def test_tarjan_returns_no_sccs(
        self, graph: dict[str, set[str]], expected: list[list[str]]
    ) -> None:
        """tarjan_scc returns no SCCs for acyclic / self-loop / disconnected graphs."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        assert tarjan_scc(graph) == expected

    def test_tarjan_iterative_multiple_sccs(self) -> None:
        """Two independent cycles both detected."""
        from axm_audit.core.rules.architecture.coupling import tarjan_scc

        graph = {
            "A": {"B"},
            "B": {"A"},
            "C": {"D"},
            "D": {"C"},
        }
        sccs = tarjan_scc(graph)
        assert len(sccs) == 2
        scc_sets = [set(scc) for scc in sccs]
        assert {"A", "B"} in scc_sets
        assert {"C", "D"} in scc_sets
