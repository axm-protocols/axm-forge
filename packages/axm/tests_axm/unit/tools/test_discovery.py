"""Unit tests for :mod:`axm.tools.discovery`, the single AXM tool resolver."""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pytest

from axm.tools.discovery import (
    TOOL_ENTRY_POINT_GROUPS,
    DuplicateToolError,
    tool_entry_points,
)

_TRIBUNAL = "axm.tribunal.tools"
_LEGACY = "axm.tools"


@dataclass(frozen=True)
class _Dist:
    name: str


@dataclass(frozen=True, eq=False)
class _EP:
    """Metadata-only stand-in for :class:`importlib.metadata.EntryPoint`."""

    name: str
    group: str
    dist: _Dist | None
    value: str = "pkg.tools:Tool"


def _ep(name: str, group: str, dist: str | None) -> _EP:
    return _EP(name, group, _Dist(dist) if dist is not None else None)


def _install(
    monkeypatch: pytest.MonkeyPatch, groups: Mapping[str, Sequence[_EP]]
) -> list[str]:
    """Serve *groups* as the installed entry points; return the queried groups."""
    queried: list[str] = []

    def _fake(*, group: str) -> list[_EP]:
        queried.append(group)
        return list(groups.get(group, ()))

    fake: Callable[..., list[_EP]] = _fake
    monkeypatch.setattr(importlib.metadata, "entry_points", fake)
    return queried


def test_groups_are_tribunal_first_then_legacy() -> None:
    assert TOOL_ENTRY_POINT_GROUPS == (_TRIBUNAL, _LEGACY)


def test_groups_queried_in_precedence_order(monkeypatch: pytest.MonkeyPatch) -> None:
    queried = _install(monkeypatch, {})
    assert tool_entry_points() == {}
    assert queried == [_TRIBUNAL, _LEGACY, "axm.tool_manifests"]


def test_name_in_both_groups_resolves_to_tribunal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tribunal = _ep("graph_run", _TRIBUNAL, "axm-lens")
    legacy = _ep("graph_run", _LEGACY, "axm-nexus-legacy")
    only_legacy = _ep("audit", _LEGACY, "axm-audit")
    _install(monkeypatch, {_TRIBUNAL: [tribunal], _LEGACY: [legacy, only_legacy]})

    with caplog.at_level(logging.DEBUG, logger="axm.tools.discovery"):
        resolved = tool_entry_points()

    assert resolved == {"audit": only_legacy, "graph_run": tribunal}
    shadowing = [r.getMessage() for r in caplog.records]
    assert shadowing == [
        "tool 'graph_run': axm-lens (axm.tribunal.tools) shadows "
        "axm-nexus-legacy (axm.tools)"
    ]


@pytest.mark.parametrize("group", [_TRIBUNAL, _LEGACY])
def test_name_twice_in_one_group_names_both_distributions(
    monkeypatch: pytest.MonkeyPatch, group: str
) -> None:
    _install(
        monkeypatch,
        {group: [_ep("audit", group, "pkg-zeta"), _ep("audit", group, "pkg-alpha")]},
    )

    with pytest.raises(DuplicateToolError) as exc:
        tool_entry_points()

    assert (exc.value.group, exc.value.name) == (group, "audit")
    assert exc.value.distributions == ("pkg-alpha", "pkg-zeta")
    assert "'pkg-alpha'" in str(exc.value)
    assert "'pkg-zeta'" in str(exc.value)


def test_legacy_duplicate_is_refused_even_when_tribunal_shadows_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        {
            _TRIBUNAL: [_ep("audit", _TRIBUNAL, "pkg-new")],
            _LEGACY: [_ep("audit", _LEGACY, "pkg-a"), _ep("audit", _LEGACY, "pkg-b")],
        },
    )
    with pytest.raises(DuplicateToolError, match=r"'axm\.tools'"):
        tool_entry_points()


def test_distribution_less_entry_point_is_named_by_its_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        {_LEGACY: [_ep("audit", _LEGACY, None), _ep("audit", _LEGACY, "pkg-a")]},
    )
    with pytest.raises(DuplicateToolError) as exc:
        tool_entry_points()
    assert "<unknown distribution of pkg.tools:Tool>" in exc.value.distributions


def test_resolution_order_is_independent_of_install_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eps = [
        _ep("zeta", _LEGACY, "p1"),
        _ep("alpha", _LEGACY, "p2"),
        _ep("mid", _LEGACY, "p3"),
    ]
    _install(monkeypatch, {_LEGACY: eps})
    forward = tool_entry_points()
    _install(monkeypatch, {_LEGACY: eps[::-1]})
    backward = tool_entry_points()

    assert list(forward) == list(backward) == ["alpha", "mid", "zeta"]
    assert forward == backward
