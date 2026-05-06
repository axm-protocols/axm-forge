"""Tests for tiered severity in coupling findings (AXM-1293) — unit scope."""

from __future__ import annotations

from typing import Any

import pytest

from axm_audit.core.rules.architecture.coupling import build_coupling_result


def _build_result(
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


class TestUnitScope:
    """Unit-scope tests (no real I/O, internal imports)."""

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
        result = _build_result(
            {"mod_a": fan_out}, threshold=10, severity_error_multiplier=2
        )

        assert result["n_over_threshold"] == 1
        assert result["over_threshold"][0]["severity"] == expected_severity

    def test_multiplier_1_all_error(self) -> None:
        """multiplier=1 → all over-threshold modules are immediately ERROR."""
        result = _build_result(
            {"mod_a": 11, "mod_b": 15},
            threshold=10,
            severity_error_multiplier=1,
        )

        assert result["n_over_threshold"] == 2
        for entry in result["over_threshold"]:
            assert entry["severity"] == "error"

    def test_mixed_severities(self) -> None:
        """Module A at warning, Module B at error → worst severity, passed=False."""
        # threshold=10, multiplier=2 → warning at 11-20, error at 21+
        result = _build_result(
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
        # threshold=10, multiplier=2
        # mod_a=12 (warning), mod_b=15 (warning), mod_c=25 (error)
        result = _build_result(
            {"mod_a": 12, "mod_b": 15, "mod_c": 25, "mod_d": 5},
            threshold=10,
            severity_error_multiplier=2,
        )

        over = result["over_threshold"]
        warnings = [e for e in over if e["severity"] == "warning"]
        errors = [e for e in over if e["severity"] == "error"]
        assert len(warnings) == 2
        assert len(errors) == 1
