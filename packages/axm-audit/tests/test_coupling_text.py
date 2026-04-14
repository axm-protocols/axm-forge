from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

_MOD = "axm_audit.core.rules.architecture"


def _make_over_entry(
    module: str,
    fan_out: int,
    effective_threshold: int,
    severity: str,
    role: str = "leaf",
) -> dict[str, Any]:
    return {
        "module": module,
        "fan_out": fan_out,
        "role": role,
        "effective_threshold": effective_threshold,
        "severity": severity,
    }


def _make_metrics(
    over: list[dict[str, Any]],
    *,
    max_fan_out: int = 20,
    max_fan_in: int = 5,
    avg_coupling: float = 8.0,
) -> dict[str, Any]:
    return {
        "max_fan_out": max_fan_out,
        "max_fan_in": max_fan_in,
        "avg_coupling": avg_coupling,
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


@pytest.fixture()
def _patch_coupling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Return a helper that patches coupling internals and runs check."""

    def _run(
        over: list[dict[str, Any]],
        n_warnings: int,
        n_errors: int,
        severity: str = "warning",
    ) -> Any:
        from axm_audit.core.rules.architecture import CouplingMetricRule

        metrics = _make_metrics(over)

        monkeypatch.setattr(
            f"{_MOD}._read_coupling_config",
            lambda _p: (12, {}, 0, 2),
        )
        monkeypatch.setattr(
            f"{_MOD}._compute_coupling_metrics",
            lambda *a, **kw: metrics,
        )
        monkeypatch.setattr(
            f"{_MOD}._resolve_coupling_severity",
            lambda _o: (n_warnings, n_errors, severity),
        )

        # Ensure check_src returns None (no early exit)
        (tmp_path / "src").mkdir(exist_ok=True)
        monkeypatch.setattr(
            CouplingMetricRule,
            "check_src",
            lambda self, _p: None,
        )

        rule = CouplingMetricRule()
        return rule.check(tmp_path)

    return _run


def test_coupling_text_format(_patch_coupling: Any) -> None:
    """text= lines match '\u2022 {leaf} fo:{N}/{T} {\u26a0|\u2718}' pattern."""
    over = [
        _make_over_entry("axm_audit.core.rules.architecture", 18, 12, "warning"),
        _make_over_entry("axm_audit.core.engine", 16, 12, "warning"),
        _make_over_entry("axm_audit.formatters", 14, 10, "error"),
    ]
    result = _patch_coupling(over, n_warnings=2, n_errors=1, severity="error")

    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 3
    assert lines[0] == "\u2022 architecture fo:18/12 \u26a0"
    assert lines[1] == "\u2022 engine fo:16/12 \u26a0"
    assert lines[2] == "\u2022 formatters fo:14/10 \u2718"


def test_coupling_text_none_when_passed(_patch_coupling: Any) -> None:
    """text=None when passed=True with 0 violations."""
    result = _patch_coupling(over=[], n_warnings=0, n_errors=0, severity="info")

    assert result.text is None
    assert result.passed is True


def test_coupling_text_single_segment_module(_patch_coupling: Any) -> None:
    """Module name without dots — rsplit returns the name as-is."""
    over = [
        _make_over_entry("utils", 15, 12, "warning"),
    ]
    result = _patch_coupling(over, n_warnings=1, n_errors=0)

    assert result.text is not None
    assert result.text == "\u2022 utils fo:15/12 \u26a0"


def test_coupling_text_mixed_severities(_patch_coupling: Any) -> None:
    """2 warnings + 1 error — each line shows correct severity symbol."""
    over = [
        _make_over_entry("pkg.alpha", 20, 12, "warning"),
        _make_over_entry("pkg.beta", 18, 12, "warning"),
        _make_over_entry("pkg.gamma", 25, 12, "error"),
    ]
    result = _patch_coupling(over, n_warnings=2, n_errors=1, severity="error")

    lines = result.text.split("\n")
    assert len(lines) == 3
    # Each line has the correct severity symbol
    warning_lines = [line for line in lines if line.endswith("\u26a0")]
    error_lines = [line for line in lines if line.endswith("\u2718")]
    assert len(warning_lines) == 2
    assert len(error_lines) == 1
    assert "\u2022 gamma fo:25/12 \u2718" in lines
