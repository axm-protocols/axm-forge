from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.coupling import (
    parse_overrides,
    read_coupling_config,
    safe_int,
)

# ---------------------------------------------------------------------------
# Unit tests — safe_int
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        pytest.param(10, 5, 10, id="valid_positive"),
        pytest.param(0, 5, 0, id="valid_zero"),
        pytest.param("abc", 5, 5, id="non_int_falls_back"),
        pytest.param(-3, 5, 5, id="negative_falls_back"),
    ],
)
def test_safe_int(value: object, default: int, expected: int) -> None:
    assert safe_int(value, default) == expected


# ---------------------------------------------------------------------------
# Unit tests — parse_overrides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        pytest.param({"mod": 15}, {"mod": 15}, id="valid_dict"),
        pytest.param({"mod": "abc"}, {}, id="invalid_value"),
        pytest.param("invalid", {}, id="not_a_dict"),
    ],
)
def test_parse_overrides(input_value: object, expected: dict[str, int]) -> None:
    assert parse_overrides(input_value) == expected


# ---------------------------------------------------------------------------
# Edge cases — read_coupling_config
# ---------------------------------------------------------------------------


def test_no_pyproject(tmp_path: Path) -> None:
    """No pyproject.toml → all defaults."""
    result = read_coupling_config(tmp_path)
    # Returns the 4-tuple of defaults
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_malformed_toml(tmp_path: Path) -> None:
    """Invalid TOML content → all defaults."""
    (tmp_path / "pyproject.toml").write_text("{{not valid toml", encoding="utf-8")
    result = read_coupling_config(tmp_path)
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_missing_coupling_section(tmp_path: Path) -> None:
    """Valid TOML without [tool.axm-audit.coupling] → all defaults."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [project]
        name = "demo"
        """),
        encoding="utf-8",
    )
    result = read_coupling_config(tmp_path)
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_zero_threshold(tmp_path: Path) -> None:
    """fan_out_threshold = 0 is valid (not negative)."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.axm-audit.coupling]
        fan_out_threshold = 0
        """),
        encoding="utf-8",
    )
    threshold, _overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
    assert threshold == 0
