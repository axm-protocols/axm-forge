"""Integration tests for :func:`axm_vault.catalog.load_catalog`.

These exercise the ``importlib.metadata.entry_points`` discovery boundary by
monkeypatching it; they never depend on real ``axm.credentials`` entry-points
(the catalog is empty by design for vault itself).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from axm_vault import catalog as catalog_module
from axm_vault.catalog import load_catalog
from tests.fixtures.sample_groups import SAMPLE_GROUPS, provide_sample_groups


class _FakeEntryPoint:
    """Minimal entry-point stub whose ``load`` returns a provider callable."""

    def __init__(self, name: str, provider: object) -> None:
        self.name = name
        self.group = "axm.credentials"
        self._provider = provider

    def load(self) -> object:
        return self._provider


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Reset the ``functools.cache`` between tests (AC5 isolation)."""
    load_catalog.cache_clear()
    yield
    load_catalog.cache_clear()


@pytest.mark.integration
def test_load_catalog_empty_when_no_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: no entry-points -> empty catalog, no raise."""
    monkeypatch.setattr(
        catalog_module, "entry_points", lambda *, group: [], raising=True
    )

    catalog = load_catalog()

    assert catalog.groups() == []


@pytest.mark.integration
def test_load_catalog_discovers_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1, AC5: entry-points are loaded, called, and indexed by id."""
    fake_ep = _FakeEntryPoint("sample", provide_sample_groups)
    monkeypatch.setattr(
        catalog_module, "entry_points", lambda *, group: [fake_ep], raising=True
    )

    catalog = load_catalog()

    assert {g.id for g in catalog.groups()} == {g.id for g in SAMPLE_GROUPS}
    assert catalog.group("broker").package == "axm-broker"
