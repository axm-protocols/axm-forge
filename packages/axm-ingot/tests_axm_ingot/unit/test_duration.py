"""Unit tests for :mod:`axm_ingot.duration` (format_duration)."""

from __future__ import annotations

import axm_ingot
from axm_ingot import format_duration


def test_sub_second_renders_in_milliseconds() -> None:
    """AC1: a sub-second duration renders in integer milliseconds."""
    assert format_duration(450) == "450ms"


def test_seconds_render_with_one_decimal() -> None:
    """AC2: a duration crossing the second threshold renders in seconds."""
    assert format_duration(1500) == "1.5s"


def test_minute_threshold_renders_in_min() -> None:
    """AC2: a duration crossing the minute threshold renders in minutes."""
    assert format_duration(90000) == "1.5min"


def test_hour_threshold_renders_in_h() -> None:
    """AC2: a duration crossing the hour threshold renders in hours."""
    assert format_duration(5400000) == "1.5h"


def test_rounds_rather_than_truncates() -> None:
    """AC2: the one-decimal output rounds (1470ms -> 1.5s, not 1.4s)."""
    assert format_duration(1470) == "1.5s"


def test_negative_input_returns_fallback_without_raising() -> None:
    """AC3: a negative input returns the fallback string, never raising."""
    assert format_duration(-5) == "n/a"


def test_exported_from_package_root() -> None:
    """AC4: format_duration is exported from the package root and in __all__."""
    assert "format_duration" in axm_ingot.__all__
    assert callable(axm_ingot.format_duration)
    assert format_duration(1) == "1ms"
