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
from tests_axm_vault.fixtures.sample_groups import SAMPLE_GROUPS, provide_sample_groups


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


def _install_mixed_distribution(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from importlib.metadata import entry_points as metadata_entry_points

    module_body = """from axm_vault import auth
from axm_vault.models import CredentialGroup, CredentialSpec

class ConnectedSource:
    def status(self):
        return auth.AuthStatus.CONNECTED

DEPENDENCY = auth.AuthDependencySpec(
    name="github-session", source=ConnectedSource()
)
GROUP = CredentialGroup(
    id="mixed",
    package="axm-mixed",
    title="Mixed",
    specs=(CredentialSpec(name="token", env="TOKEN", kind="token"),),
    auth_dependencies=(DEPENDENCY,),
)

def provide():
    return [GROUP]
"""
    tmp_path.joinpath("mixed_provider.py").write_text(module_body, encoding="utf-8")
    metadata = tmp_path / "axm_vault_auth_fixture-1.0.dist-info"
    metadata.mkdir()
    metadata.joinpath("METADATA").write_text(
        "Metadata-Version: 2.1\nName: axm-vault-auth-fixture\nVersion: 1.0\n",
        encoding="utf-8",
    )
    metadata.joinpath("entry_points.txt").write_text(
        "[axm.credentials]\nmixed-test = mixed_provider:provide\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    def fixture_entry_points(*, group: str) -> list[object]:
        return [
            endpoint
            for endpoint in metadata_entry_points(group=group)
            if endpoint.name == "mixed-test"
        ]

    monkeypatch.setattr(catalog_module, "entry_points", fixture_entry_points)


@pytest.mark.integration
def test_load_catalog_discovers_auth_dependencies_from_distribution(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6: disk-discovered axm.credentials entries carry auth dependencies."""
    _install_mixed_distribution(tmp_path, monkeypatch)

    catalog = load_catalog()

    assert {dependency.name for dependency in catalog.auth_dependencies()} == {
        "github-session"
    }


@pytest.mark.integration
def test_load_catalog_keeps_discovered_kinds_separate(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a loaded catalog never mixes auth dependencies into credentials."""
    _install_mixed_distribution(tmp_path, monkeypatch)

    catalog = load_catalog()

    credential_names = {spec.name for _group_id, spec in catalog.all_specs()}
    assert credential_names == {"token"}
    assert "github-session" not in credential_names
