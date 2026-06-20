"""Unit tests for the axm-ast-backed node god-class and coupling rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.framework import Framework
from axm_audit.core.rules.node import coupling as coupling_module
from axm_audit.core.rules.node.coupling import NodeCouplingRule, NodeGodClassRule


class _FakePkg:
    """Stand-in PackageInfo (the rules only pass it to the metric functions)."""


def test_rule_ids_and_framework() -> None:
    """The rules share the Python rule_ids and register under node."""
    assert NodeGodClassRule().rule_id == "ARCH_GOD_CLASS"
    assert NodeCouplingRule().rule_id == "ARCH_COUPLING"
    assert NodeGodClassRule().framework is Framework.NODE


def test_non_node_dir_skips(tmp_path: Path) -> None:
    """A directory without package.json is skipped, not failed."""
    result = NodeGodClassRule().check(tmp_path)
    assert result.passed is True
    assert "skipped" in result.message.lower()


def test_god_class_scores_by_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each god class deducts 15 points."""
    (tmp_path / "package.json").write_text("{}")
    from axm_ast.core.metrics import GodClass

    monkeypatch.setattr(coupling_module, "_analyze", lambda _p: _FakePkg())
    monkeypatch.setattr(
        "axm_ast.core.metrics.find_god_classes",
        lambda _pkg: [GodClass(name="Big", file="a.ts", lines=600, methods=20)],
    )
    result = NodeGodClassRule().check(tmp_path)
    assert result.score == 85
    assert result.passed is False


def test_coupling_flags_over_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A module over the fan-out threshold fails the coupling rule."""
    (tmp_path / "package.json").write_text("{}")
    from axm_ast.core.metrics import CouplingMetrics, ModuleCoupling

    metrics = CouplingMetrics(
        per_module=[ModuleCoupling(module="hub", fan_in=0, fan_out=12)],
        max_fan_out=12,
        max_fan_in=0,
    )
    monkeypatch.setattr(coupling_module, "_analyze", lambda _p: _FakePkg())
    monkeypatch.setattr("axm_ast.core.metrics.compute_coupling", lambda _pkg: metrics)
    result = NodeCouplingRule().check(tmp_path)
    assert result.passed is False
    assert result.score == 95


def test_unavailable_backend_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When axm-ast cannot analyse, the rule fails loud (never green)."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(coupling_module, "_analyze", lambda _p: None)
    result = NodeCouplingRule().check(tmp_path)
    assert result.passed is False
    assert "not available" in result.message.lower()
