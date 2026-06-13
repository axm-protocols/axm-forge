"""Unit tests for axm.tools._discovery.entry_points_for."""

from __future__ import annotations

import importlib.metadata

import pytest

from axm.tools._discovery import entry_points_for


class _FakeEP:
    """Minimal stand-in for importlib.metadata.EntryPoint (name only)."""

    def __init__(self, name: str) -> None:
        self.name = name


def test_entry_points_for_maps_name_to_ep(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC3: returns a {name: EntryPoint} mapping for the group."""
    ep_a = _FakeEP("alpha")
    ep_b = _FakeEP("beta")
    captured: dict[str, str] = {}

    def _fake_entry_points(*, group: str) -> list[_FakeEP]:
        captured["group"] = group
        return [ep_a, ep_b]

    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points)

    result = entry_points_for("axm.tools")

    assert result == {"alpha": ep_a, "beta": ep_b}
    assert captured["group"] == "axm.tools"


def test_entry_points_for_empty_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: returns an empty mapping when the group has no entry points."""

    def _fake_entry_points(*, group: str) -> list[_FakeEP]:
        return []

    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points)

    assert entry_points_for("nonexistent.group") == {}
