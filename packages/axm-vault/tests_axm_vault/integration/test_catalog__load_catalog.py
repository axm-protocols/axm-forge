"""Integration tests for :func:`axm_vault.catalog.load_catalog`.

These exercise the ``importlib.metadata.entry_points`` discovery boundary by
monkeypatching it; they never depend on real ``axm.credentials`` entry-points
(the catalog is empty by design for vault itself).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from importlib import invalidate_caches
from importlib.metadata import entry_points as metadata_entry_points
from pathlib import Path

import pytest

import axm_vault
from axm_vault import catalog as catalog_module
from axm_vault.catalog import load_catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
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
    name="github-session",
    source=ConnectedSource(),
    login_command="gh auth login",
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


def _install_resilient_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok_module = """from axm_vault.models import CredentialGroup, CredentialSpec

GROUP = CredentialGroup(
    id="survivor",
    package="axm-survivor",
    title="Survivor",
    specs=(CredentialSpec(
        name="token",
        env="AXM_VAULT_SURVIVOR_TOKEN",
        kind="token",
        required=False,
    ),),
)

def groups():
    return [GROUP]
"""
    tmp_path.joinpath("fake_ok.py").write_text(ok_module, encoding="utf-8")
    tmp_path.joinpath("fake_broken.py").write_text(
        "ALREADY_BUILT = object()\n", encoding="utf-8"
    )

    distributions = (
        ("ok-fixture", "ok = fake_ok:groups"),
        ("broken-fixture", "broken = fake_broken:ALREADY_BUILT"),
    )
    for distribution_name, declaration in distributions:
        metadata = tmp_path / f"{distribution_name}-1.0.dist-info"
        metadata.mkdir()
        metadata.joinpath("METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution_name}\nVersion: 1.0\n",
            encoding="utf-8",
        )
        metadata.joinpath("entry_points.txt").write_text(
            f"[axm.credentials]\n{declaration}\n",
            encoding="utf-8",
        )

    monkeypatch.syspath_prepend(str(tmp_path))
    invalidate_caches()

    def fixture_entry_points(*, group: str) -> list[object]:
        return [
            endpoint
            for endpoint in metadata_entry_points(group=group)
            if endpoint.name in {"ok", "broken"}
        ]

    monkeypatch.setattr(catalog_module, "entry_points", fixture_entry_points)
    load_catalog.cache_clear()


@pytest.mark.integration
def test_load_catalog_keeps_conforming_disk_contribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: one malformed disk contribution does not hide a conforming one."""
    _install_resilient_distribution(tmp_path, monkeypatch)

    catalog = load_catalog()

    assert "survivor" in {group.id for group in catalog.groups()}


@pytest.mark.integration
def test_load_catalog_reports_malformed_disk_contribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: the malformed entry point remains visible as a typed rejection."""
    _install_resilient_distribution(tmp_path, monkeypatch)

    catalog = load_catalog()

    assert any(
        rejection.entry_point == "broken" and rejection.reason
        for rejection in catalog.rejections()
    )


@pytest.mark.integration
def test_load_catalog_warns_for_malformed_disk_contribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC6: skipping a malformed entry point emits a named warning."""
    _install_resilient_distribution(tmp_path, monkeypatch)

    with caplog.at_level(logging.WARNING, logger="axm_vault.catalog"):
        load_catalog()

    assert any(
        record.levelno >= logging.WARNING and "broken" in record.getMessage()
        for record in caplog.records
    )


def _secret_group(gid: str, spec_name: str = "api_key") -> CredentialGroup:
    return CredentialGroup(
        id=gid,
        package=f"pkg-{gid.lower()}",
        title="Service",
        specs=(
            CredentialSpec(
                name=spec_name,
                env="SVC_TOKEN",
                kind="token",
                sensitivity=Sensitivity.SECRET,
                required=False,
            ),
        ),
    )


_CODEX = _secret_group("codex")
_SAIN = _secret_group("sain")
_BAD_ID = _secret_group("Bad_ID")
_BADSPEC = _secret_group("badspec", "Bad-Key")


def _provide_ok() -> list[CredentialGroup]:
    return [_CODEX]


def _provide_bad_id() -> list[CredentialGroup]:
    return [_BAD_ID]


def _provide_badspec() -> list[CredentialGroup]:
    return [_BADSPEC]


def _provide_sain_and_bad_id() -> list[CredentialGroup]:
    return [_SAIN, _BAD_ID]


def _provide_sain_and_badspec() -> list[CredentialGroup]:
    return [_SAIN, _BADSPEC]


def _install_ok_and_bad(monkeypatch: pytest.MonkeyPatch, bad_provider: object) -> None:
    endpoints = [
        _FakeEntryPoint("ok", _provide_ok),
        _FakeEntryPoint("bad", bad_provider),
    ]
    monkeypatch.setattr(
        catalog_module, "entry_points", lambda *, group: endpoints, raising=True
    )
    load_catalog.cache_clear()


def _assert_only_bad_rejected(offender: str) -> None:
    catalog = load_catalog()
    assert {g.id for g in catalog.groups()} == {"codex"}
    assert catalog.group("codex") == _CODEX
    rejections = catalog.rejections()
    assert len(rejections) == 1
    assert rejections[0].entry_point == "bad"
    assert offender in rejections[0].reason


@pytest.mark.integration
def test_load_catalog_rejects_contribution_with_invalid_group_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: an invalid group id rejects only its contribution, without raising."""
    _install_ok_and_bad(monkeypatch, _provide_bad_id)

    _assert_only_bad_rejected("Bad_ID")


@pytest.mark.integration
def test_load_catalog_rejects_contribution_with_invalid_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an invalid SECRET spec key rejects only its contribution."""
    _install_ok_and_bad(monkeypatch, _provide_badspec)

    _assert_only_bad_rejected("Bad-Key")


@pytest.mark.integration
def test_load_catalog_drops_valid_sibling_of_invalid_group_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: the valid sibling 'sain' of an invalid group id is dropped too."""
    _install_ok_and_bad(monkeypatch, _provide_sain_and_bad_id)

    _assert_only_bad_rejected("Bad_ID")


@pytest.mark.integration
def test_load_catalog_drops_valid_sibling_of_invalid_spec_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: the valid sibling 'sain' of an invalid spec key is dropped too."""
    _install_ok_and_bad(monkeypatch, _provide_sain_and_badspec)

    _assert_only_bad_rejected("Bad-Key")


@pytest.mark.integration
@pytest.mark.parametrize(
    "bad_provider",
    [
        _provide_bad_id,
        _provide_badspec,
        _provide_sain_and_bad_id,
        _provide_sain_and_badspec,
    ],
    ids=["bad-id", "badspec", "sain-bad-id", "sain-badspec"],
)
def test_public_judgement_matches_load_catalog_rejection(
    monkeypatch: pytest.MonkeyPatch,
    bad_provider: object,
) -> None:
    """AC7: the public judgement yields the exact rejection load_catalog records."""
    _install_ok_and_bad(monkeypatch, bad_provider)

    rejections = load_catalog().rejections()
    assert len(rejections) == 1

    assert axm_vault.groups_from_provider("bad", bad_provider) == (
        (),
        rejections[0],
    )
