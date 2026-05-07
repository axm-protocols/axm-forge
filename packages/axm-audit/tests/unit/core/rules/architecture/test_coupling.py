"""Unit tests for axm_audit.core.rules.architecture.coupling."""

from __future__ import annotations

from axm_audit.core.rules.architecture.coupling import build_coupling_result


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
