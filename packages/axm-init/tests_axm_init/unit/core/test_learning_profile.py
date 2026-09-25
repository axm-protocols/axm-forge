"""Learning metadata is routed verbatim to the installed provider's hooks."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from axm_init import scaffolding
from axm_init.core import learning_profile


def _install(monkeypatch: pytest.MonkeyPatch, provider: object) -> None:
    entry = Mock(spec=EntryPoint)
    entry.load.return_value = Mock(return_value=provider)
    monkeypatch.setattr(scaffolding, "entry_points", Mock(return_value=[entry]))


def _provider(**hooks: object) -> SimpleNamespace:
    return SimpleNamespace(layers=Mock(return_value=()), **hooks)


def test_merge_forwards_arguments_and_returns_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: merging is the provider's, with arguments passed through unchanged."""
    hook = Mock(return_value="merged")
    _install(monkeypatch, _provider(merge_learning_metadata=hook))

    merged = learning_profile.merge_learning_metadata("[project]\n", "vision", "demo")

    assert merged == "merged"
    hook.assert_called_once_with("[project]\n", "vision", "demo")


def test_declared_domain_forwards_the_requested_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: discovery hands the provider both the root and the requested domain."""
    hook = Mock(return_value="vision")
    _install(monkeypatch, _provider(declared_learning_domain=hook))
    root = Path("/project")

    assert learning_profile.declared_learning_domain(root, "vision") == "vision"
    hook.assert_called_once_with(root, "vision")


def test_register_forwards_root_domain_and_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: registration is delegated with its three arguments."""
    hook = Mock(return_value=None)
    _install(monkeypatch, _provider(register_learning_profile=hook))
    root = Path("/project")

    learning_profile.register_learning_profile(root, "vision", "demo")

    hook.assert_called_once_with(root, "vision", "demo")


def test_provider_without_the_hook_names_the_missing_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: an outdated provider fails with the missing hook's name."""
    _install(monkeypatch, _provider())

    with pytest.raises(scaffolding.ProviderError, match="merge_learning_metadata"):
        learning_profile.merge_learning_metadata("", "vision", "demo")
