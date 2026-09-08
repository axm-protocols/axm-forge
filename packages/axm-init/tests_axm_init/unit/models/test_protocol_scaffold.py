from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError


def _protocol_scaffold() -> Any:
    return importlib.import_module("axm_init.models.protocol_scaffold")


def _valid_payload() -> dict[str, Any]:
    return {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [
            {"name": "work_request"},
            {"name": "work_result"},
        ],
        "prompts": [
            {"name": "implement", "text": "Implement the requested change."},
            {"name": "review", "text": "Review the implementation."},
        ],
        "nodes": [
            {
                "name": "implementation",
                "contract": "work_result",
                "prompt": "implement",
            },
            {
                "name": "review",
                "contract": "work_result",
                "prompt": "review",
            },
        ],
        "phases": [
            {"name": "build", "nodes": ["implementation"]},
            {"name": "verify", "nodes": ["review"]},
        ],
        "ticket": {
            "ticket_type": "dev.work",
            "input_contract": "work_request",
        },
    }


def _declare(**overrides: Any) -> Any:
    payload = _valid_payload()
    payload.update(overrides)
    return _protocol_scaffold().ProtocolScaffoldDecl(**payload)


def test_valid_declaration_derives_all_public_names() -> None:
    """AC1: valid components retain inputs and derive every public name."""
    declaration = _declare()

    assert declaration.graph_name == "dev.work.exec"
    assert [item.name for item in declaration.contracts] == [
        "work_request",
        "work_result",
    ]
    assert [item.model_name for item in declaration.contracts] == [
        "WorkRequest",
        "WorkResult",
    ]
    assert [item.factory_name for item in declaration.nodes] == [
        "build_implementation",
        "build_review",
    ]
    assert [item.factory_name for item in declaration.phases] == [
        "build_build",
        "build_verify",
    ]
    assert [item.name for item in declaration.prompts] == ["implement", "review"]


def test_derived_names_cannot_be_supplied_as_inputs() -> None:
    """AC1: graph, model, and factory names are output-only derived values."""
    mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda data: data.update(graph_name="overridden.graph.name"),
        lambda data: data["contracts"][0].update(model_name="Override"),
        lambda data: data["nodes"][0].update(factory_name="build_override"),
        lambda data: data["phases"][0].update(factory_name="build_override"),
    )

    for mutate in mutations:
        payload = _valid_payload()
        mutate(payload)
        with pytest.raises(ValidationError):
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)


def test_invalid_identifier_segments_are_rejected() -> None:
    """AC2: unsafe or non-lowercase Python identifier segments are invalid."""
    for invalid_segment in ("dev/work", "..", "/dev", "class", "Dev", "dev-lab"):
        with pytest.raises(ValidationError):
            _declare(domain=invalid_segment)


def test_duplicate_and_derived_name_collisions_are_rejected() -> None:
    """AC3: duplicate components and cross-kind public-name collisions fail."""
    duplicate_payload = _valid_payload()
    duplicate_payload["contracts"].append({"name": "work_request"})
    with pytest.raises(ValidationError):
        _protocol_scaffold().ProtocolScaffoldDecl(**duplicate_payload)

    collision_payload = _valid_payload()
    collision_payload["nodes"][0]["name"] = "build"
    with pytest.raises(ValidationError):
        _protocol_scaffold().ProtocolScaffoldDecl(**collision_payload)

    collision_payload["phases"][0]["name"] = "assemble"
    declaration = _protocol_scaffold().ProtocolScaffoldDecl(**collision_payload)
    assert declaration.nodes[0].factory_name == "build_build"
    assert declaration.phases[0].factory_name == "build_assemble"


def test_ticket_binding_is_validated_independently_from_graph_name() -> None:
    """AC4: ticket bindings are required and need only reference a contract."""
    missing_binding = _valid_payload()
    missing_binding["ticket"] = {"ticket_type": "dev.work"}
    with pytest.raises(ValidationError):
        _protocol_scaffold().ProtocolScaffoldDecl(**missing_binding)

    unknown_binding = _valid_payload()
    unknown_binding["ticket"]["input_contract"] = "unknown_request"
    with pytest.raises(ValidationError):
        _protocol_scaffold().ProtocolScaffoldDecl(**unknown_binding)

    declaration = _declare(
        ticket={
            "ticket_type": "support.case.triage",
            "input_contract": "work_request",
        }
    )
    assert declaration.ticket.ticket_type == "support.case.triage"
    assert declaration.ticket.input_contract == "work_request"
    assert declaration.ticket.ticket_type != declaration.graph_name


def test_extra_fields_are_forbidden() -> None:
    """AC5: every declaration model rejects undeclared input fields."""
    invalid_payloads = []

    top_level = _valid_payload()
    top_level["unexpected"] = True
    invalid_payloads.append(top_level)

    for component in ("contracts", "prompts", "nodes", "phases"):
        payload = _valid_payload()
        payload[component][0]["unexpected"] = True
        invalid_payloads.append(payload)

    ticket = _valid_payload()
    ticket["ticket"]["unexpected"] = True
    invalid_payloads.append(ticket)

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)


def test_domain_and_action_vocabulary_is_open() -> None:
    """AC6: novel structurally valid domain and action values are accepted."""
    declaration = _declare(
        domain="culinary_lab",
        unit="menu",
        action="ferment",
        ticket={
            "ticket_type": "kitchen.batch",
            "input_contract": "work_request",
        },
    )

    assert declaration.graph_name == "culinary_lab.menu.ferment"
