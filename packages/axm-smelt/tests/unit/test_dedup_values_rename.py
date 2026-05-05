from __future__ import annotations

import pytest

from axm_smelt.strategies import REGISTRY
from axm_smelt.strategies.dedup_values import DedupValuesStrategy


def test_dedup_strategy_new_name() -> None:
    assert DedupValuesStrategy().name == "dedup_values_with_refs"


def test_registry_resolves_new_name() -> None:
    assert REGISTRY["dedup_values_with_refs"] is DedupValuesStrategy


def test_registry_rejects_old_name() -> None:
    with pytest.raises(KeyError):
        REGISTRY["dedup_values"]
