from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture.coupling import (
    parse_overrides,
    read_coupling_config,
    safe_int,
)

# ---------------------------------------------------------------------------
# Unit tests — safe_int
# ---------------------------------------------------------------------------


def test_safe_int_valid() -> None:
    assert safe_int(10, 5) == 10


def test_safe_int_string() -> None:
    assert safe_int("abc", 5) == 5


def test_safe_int_negative() -> None:
    assert safe_int(-3, 5) == 5


# ---------------------------------------------------------------------------
# Unit tests — parse_overrides
# ---------------------------------------------------------------------------


def test_parse_overrides_valid() -> None:
    assert parse_overrides({"mod": 15}) == {"mod": 15}


def test_parse_overrides_invalid_value() -> None:
    assert parse_overrides({"mod": "abc"}) == {}


def test_parse_overrides_not_dict() -> None:
    assert parse_overrides("invalid") == {}


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
