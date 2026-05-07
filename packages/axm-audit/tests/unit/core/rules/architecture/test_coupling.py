"""Unit tests for axm_audit.core.rules.architecture.coupling."""

from __future__ import annotations

import pytest

from axm_audit.core.rules.architecture.coupling import (
    build_coupling_result,
    parse_overrides,
    safe_int,
)


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
