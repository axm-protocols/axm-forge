"""Forge routes explicit Learning validation; its rules live in Learning."""

import pytest

from axm_init import scaffolding
from axm_init.checks.learning import check_learning_profile
from axm_init.core.checker import ALL_CHECKS


def test_learning_is_explicit_only():
    assert "learning" not in ALL_CHECKS


def test_learning_check_requires_installed_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(scaffolding, "load_provider", lambda kind: None)
    with pytest.raises(scaffolding.ProviderError, match="axm-learning"):
        check_learning_profile(tmp_path)
