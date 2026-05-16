"""Integration tests: axm hook entry point discoverability via importlib.metadata."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

from axm_git.hooks.commit_phase import CommitPhaseHook
from axm_git.hooks.preflight import PreflightHook

pytestmark = pytest.mark.integration


def test_preflight_hook_discoverable() -> None:
    eps = entry_points(group="axm.hooks")
    names = [ep.name for ep in eps]
    assert "git:preflight" in names


def test_commit_phase_hook_discoverable() -> None:
    eps = entry_points(group="axm.hooks")
    names = [ep.name for ep in eps]
    assert "git:commit-phase" in names


def test_preflight_hook_loads() -> None:
    eps = entry_points(group="axm.hooks")
    ep = next(ep for ep in eps if ep.name == "git:preflight")
    assert ep.load() is PreflightHook


def test_commit_phase_hook_loads() -> None:
    eps = entry_points(group="axm.hooks")
    ep = next(ep for ep in eps if ep.name == "git:commit-phase")
    assert ep.load() is CommitPhaseHook
