from __future__ import annotations

import io
import sys
from collections.abc import Sequence

import pytest

import axm_vault
from axm_vault import CredentialGroup


class MemoryInstanceSource:
    def __init__(self, instances: Sequence[str] = ()) -> None:
        self.instances = list(instances)
        self.declarations: list[str] = []
        self.secret_values: list[str] = []

    def list_instances(self) -> list[str]:
        return list(self.instances)

    def declare(self, instance: str) -> None:
        self.declarations.append(instance)
        self.instances.append(instance)


def make_group(
    *,
    source: MemoryInstanceSource | None = None,
    multi: bool = True,
) -> CredentialGroup:
    return CredentialGroup(
        id="mail",
        package="axm-mail",
        title="Mail",
        specs=(),
        multi=multi,
        instances=source,
    )


def test_list_instances_preserves_source_names_and_order() -> None:
    """AC1: enumeration preserves the source names and their exact order."""
    source = MemoryInstanceSource(["perso", "pro"])
    group = make_group(source=source)

    assert axm_vault.list_instances(group) == ["perso", "pro"]


def test_list_instances_returns_empty_for_multi_group_without_source() -> None:
    """AC2: a multi group without a source has an empty enumeration."""
    group = make_group(source=None, multi=True)

    assert axm_vault.list_instances(group) == []


def test_declare_instance_adds_name_without_receiving_a_secret() -> None:
    """AC3: declaration adds only the instance name, never a secret value."""
    source = MemoryInstanceSource(["perso"])
    group = make_group(source=source)

    axm_vault.declare_instance(group, "pro")

    assert "pro" in axm_vault.list_instances(group)
    assert source.declarations == ["pro"]
    assert source.secret_values == []


def test_declare_instance_is_non_interactive_at_stdin_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: declaration succeeds when standard input is already at EOF."""
    source = MemoryInstanceSource()
    group = make_group(source=source)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    axm_vault.declare_instance(group, "pro")

    assert "pro" in axm_vault.list_instances(group)


def test_declare_instance_without_source_raises_typed_error() -> None:
    """AC5: an unsupported declaration names the group in its typed error."""
    group = make_group(source=None)

    with pytest.raises(
        axm_vault.UnsupportedInstanceDeclarationError,
        match="mail",
    ):
        axm_vault.declare_instance(group, "pro")
