from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.architecture import CouplingMetricRule

_MOD = "axm_audit.core.rules.architecture"


def _make_metrics(
    over: list[dict[str, Any]],
    *,
    max_fo: int = 18,
    max_fi: int = 5,
    avg: float = 6.5,
) -> dict[str, Any]:
    return {
        "max_fan_out": max_fo,
        "max_fan_in": max_fi,
        "avg_coupling": avg,
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


def _patch_coupling(
    monkeypatch: pytest.MonkeyPatch,
    over: list[dict[str, Any]],
    *,
    n_warnings: int = 0,
    n_errors: int = 0,
    max_fo: int = 18,
) -> None:
    monkeypatch.setattr(
        f"{_MOD}.read_coupling_config",
        lambda _path: (12, {}, 0, 2),
    )
    monkeypatch.setattr(
        f"{_MOD}._compute_coupling_metrics",
        lambda *a, **kw: _make_metrics(over, max_fo=max_fo),
    )
    severity = "error" if n_errors else ("warning" if n_warnings else "info")
    monkeypatch.setattr(
        f"{_MOD}._resolve_coupling_severity",
        lambda _over: (n_warnings, n_errors, severity),
    )


@pytest.fixture()
def _src_dir(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


class TestCouplingTextFormat:
    """AC1: text= lines use format '\u2022 {leaf} fo:{N}/{T} {symbol}'."""

    def test_coupling_text_format(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        over = [
            {
                "module": "axm_audit.core.rules.architecture",
                "fan_out": 18,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "axm_audit.core.engine",
                "fan_out": 16,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "axm_audit.formatters",
                "fan_out": 14,
                "role": "leaf",
                "effective_threshold": 10,
                "severity": "error",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=2, n_errors=1)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        assert lines[0] == "\u2022 architecture fo:18/12 \u26a0"
        assert lines[1] == "\u2022 engine fo:16/12 \u26a0"
        assert lines[2] == "\u2022 formatters fo:14/10 \u2718"

    def test_coupling_text_none_when_passed(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        _patch_coupling(monkeypatch, [], n_warnings=0, n_errors=0, max_fo=8)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is None


class TestCouplingTextEdgeCases:
    """Edge cases for text rendering."""

    def test_single_segment_module_name(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        """Module name without dots — rsplit returns the name unchanged."""
        over = [
            {
                "module": "utils",
                "fan_out": 15,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=1, n_errors=0, max_fo=15)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        assert result.text == "\u2022 utils fo:15/12 \u26a0"

    def test_mixed_severities(
        self, monkeypatch: pytest.MonkeyPatch, _src_dir: Path
    ) -> None:
        """2 warnings + 1 error — each line shows correct severity symbol."""
        over = [
            {
                "module": "pkg.alpha",
                "fan_out": 20,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
            {
                "module": "pkg.beta",
                "fan_out": 18,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "error",
            },
            {
                "module": "pkg.gamma",
                "fan_out": 14,
                "role": "leaf",
                "effective_threshold": 12,
                "severity": "warning",
            },
        ]
        _patch_coupling(monkeypatch, over, n_warnings=2, n_errors=1)

        rule = CouplingMetricRule()
        result = rule.check(_src_dir)

        assert result.text is not None
        lines = result.text.split("\n")
        assert lines[0] == "\u2022 alpha fo:20/12 \u26a0"
        assert lines[1] == "\u2022 beta fo:18/12 \u2718"
        assert lines[2] == "\u2022 gamma fo:14/12 \u26a0"
