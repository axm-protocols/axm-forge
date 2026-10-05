"""Pure shared-unit resolution and metadata contracts."""

from __future__ import annotations

import tomllib

import pytest
from pydantic import ValidationError

from axm_init.core.protocol_unit import merge_protocol_unit, resolve_protocol_unit
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl, ProtocolUnitDecl

METADATA = '[tool.axm-init.protocols]\nschema_version = 1\ndomain = "ml"\n'


def _shared() -> ProtocolUnitDecl:
    return ProtocolUnitDecl.model_validate(
        {
            "domain": "ml",
            "unit": "run",
            "contracts": [{"name": "context"}],
            "ticket": {
                "ticket_type": "ml.run",
                "input_contract": "context",
                "entry_action": "exec",
            },
        }
    )


def _action(unit: str = "run", reference: str = "ml.run") -> ProtocolScaffoldDecl:
    return ProtocolScaffoldDecl.model_validate(
        {
            "domain": "ml",
            "unit": unit,
            "action": "exec",
            "contracts": [],
            "nodes": [],
            "unit_ticket": reference,
        }
    )


def test_resolve_shared_unit_uses_persisted_binding() -> None:
    shared = _shared()
    merged = merge_protocol_unit(METADATA, shared)
    assert resolve_protocol_unit(merged, (_action(),), None) == shared
    assert merge_protocol_unit(merged, shared) == merged
    profile = tomllib.loads(merged)["tool"]["axm-init"]["protocols"]
    assert profile["schema_version"] == 2
    assert profile["units"][0]["ticket_type"] == "ml.run"
    assert profile["units"][0]["entry_action"] == "exec"


@pytest.mark.parametrize("unit,reference", [("study", "ml.run"), ("run", "ml.unknown")])
def test_resolve_shared_unit_refuses_nonlocal_reference(
    unit: str, reference: str
) -> None:
    merged = merge_protocol_unit(METADATA, _shared())
    with pytest.raises(ValueError, match="this domain/unit"):
        resolve_protocol_unit(merged, (_action(unit, reference),), None)


def test_resolve_shared_unit_rejects_changed_persisted_declaration() -> None:
    shared = _shared()
    merged = merge_protocol_unit(METADATA, shared)
    changed = shared.model_copy(
        update={"ticket": shared.ticket.model_copy(update={"entry_action": "inspect"})}
    )
    with pytest.raises(ValueError, match="conflicts with persisted"):
        resolve_protocol_unit(merged, (_action(),), changed)


def test_resolve_shared_unit_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        resolve_protocol_unit(METADATA.replace("= 1", "= 3"), (_action(),), _shared())


@pytest.mark.parametrize("change", ["extra", "context", "entry", "same_identity"])
def test_shared_unit_declaration_is_strict(change: str) -> None:
    payload = _shared().model_dump()
    if change == "extra":
        payload["unknown"] = True
    elif change == "context":
        payload["ticket"]["input_contract"] = "unknown"
    elif change == "entry":
        payload["ticket"]["entry_action"] = "../escape"
    elif change == "same_identity":
        payload["ticket"]["ticket_type"] = "ml.run.exec"
    with pytest.raises(ValidationError):
        ProtocolUnitDecl.model_validate(payload)


def test_resolve_shared_unit_requires_declared_entry_action() -> None:
    action = _action().model_copy(update={"action": "inspect"})
    with pytest.raises(ValueError, match="entry_action must be declared"):
        resolve_protocol_unit(METADATA, (action,), _shared())


def test_resolve_shared_unit_refuses_local_ticket_claiming_another_shared_unit() -> (
    None
):
    merged = merge_protocol_unit(METADATA, _shared())
    local = ProtocolScaffoldDecl.model_validate(
        {
            "domain": "ml",
            "unit": "study",
            "action": "exec",
            "contracts": [{"name": "context"}],
            "nodes": [],
            "ticket": {"ticket_type": "ml.run", "input_contract": "context"},
        }
    )
    with pytest.raises(ValueError, match="local ticket conflicts"):
        resolve_protocol_unit(merged, (local,), None)
