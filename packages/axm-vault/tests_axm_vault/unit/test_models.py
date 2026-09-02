"""Unit tests for axm_vault.models — value-less credential catalog schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_vault import models
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity


def test_sensitivity_members() -> None:
    """AC1: Sensitivity is a StrEnum with SECRET/CONFIG/NONSENSITIVE str values."""
    assert Sensitivity.SECRET.value == "secret"
    assert Sensitivity.CONFIG.value == "config"
    assert Sensitivity.NONSENSITIVE.value == "nonsensitive"
    assert isinstance(Sensitivity.SECRET, str)


def test_spec_frozen_and_forbids_extra() -> None:
    """AC3: CredentialSpec is frozen (mutation raises) and forbids extra kwargs."""
    spec = CredentialSpec(name="api_key", env="API_KEY", kind="token")
    with pytest.raises(ValidationError):
        spec.name = "other"
    with pytest.raises(ValidationError):
        CredentialSpec(name="api_key", env="API_KEY", kind="token", bogus=1)  # type: ignore[call-arg]


def test_spec_defaults() -> None:
    """AC3: minimal spec — sensitivity==SECRET, required True, aliases==()."""
    spec = CredentialSpec(name="api_key", env="API_KEY", kind="token")
    assert spec.sensitivity == Sensitivity.SECRET
    assert spec.required is True
    assert spec.aliases == ()
    assert spec.default is None
    assert spec.prompt is None


def test_group_spec_lookup() -> None:
    """AC4: CredentialGroup.spec(name) returns the matching spec."""
    a = CredentialSpec(name="api_key", env="API_KEY", kind="token")
    b = CredentialSpec(name="secret", env="SECRET", kind="token")
    group = CredentialGroup(id="acme", package="axm-acme", title="Acme", specs=(a, b))
    assert group.spec("api_key") is a
    assert group.spec("secret") is b


def test_group_spec_unknown_raises_keyerror() -> None:
    """AC1: spec(name) raises KeyError with a contextual, group-qualified message."""
    group = CredentialGroup(id="acme", package="axm-acme", title="Acme", specs=())
    with pytest.raises(KeyError, match=r"unknown credential acme\.'nope'"):
        group.spec("nope")


def test_group_preserves_instance_source() -> None:
    """AC1: a multi-instance group preserves its declared instance source."""

    class MemoryInstanceSource:
        def list_instances(self) -> tuple[str, ...]:
            return ("personal",)

        def declare(self, instance: str) -> None:
            del instance

    source = MemoryInstanceSource()
    spec = CredentialSpec(name="token", env="MAIL_TOKEN", kind="token")

    group = CredentialGroup(
        id="mail",
        package="axm-mail",
        title="Mail",
        specs=[spec],
        multi=True,
        instances=source,
    )

    assert group.instances is source


def test_instance_source_runtime_protocol() -> None:
    """AC2: InstanceSource runtime checks require list_instances and declare."""

    class CompleteSource:
        def list_instances(self) -> tuple[str, ...]:
            return ()

        def declare(self, instance: str) -> None:
            del instance

    class SourceWithoutDeclare:
        def list_instances(self) -> tuple[str, ...]:
            return ()

    assert isinstance(CompleteSource(), models.InstanceSource)
    assert not isinstance(SourceWithoutDeclare(), models.InstanceSource)
