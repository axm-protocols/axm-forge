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
    collision_payload["phases"][0]["nodes"] = ["build"]
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


def _validation_messages(error: ValidationError) -> str:
    return " ".join(
        f"{item['loc']} {item['type']} {item['msg']}" for item in error.errors()
    )


def test_node_accepts_omitted_prompt() -> None:
    """AC1: a deterministic node may omit its prompt reference."""
    node = _protocol_scaffold().NodeDecl(name="load", contract="work_result")

    assert node.prompt is None


def test_node_accepts_omitted_input_contract() -> None:
    """AC2: a node may omit its local input-contract reference."""
    node = _protocol_scaffold().NodeDecl(name="notify", prompt="announce")

    assert node.contract is None


def test_protocol_accepts_omitted_optional_component_lists_and_ticket() -> None:
    """AC3: prompts, phases, and the complete ticket block are optional."""
    declaration = _protocol_scaffold().ProtocolScaffoldDecl(
        domain="dev",
        unit="work",
        action="exec",
        contracts=[{"name": "work_request"}],
        nodes=[],
    )

    assert declaration.prompts == []
    assert declaration.phases == []
    assert declaration.ticket is None


def test_phase_accepts_omitted_nodes() -> None:
    """AC4: a phase may omit its node collection."""
    phase = _protocol_scaffold().PhaseDecl(name="build")

    assert phase.nodes == []


def test_canonical_mixed_protocol_declaration() -> None:
    """AC5: the canonical mixed protocol validates independently of ticket type."""
    payload = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [
            {"name": name}
            for name in (
                "work_request",
                "context",
                "plan",
                "implementation",
                "review",
                "work_result",
            )
        ],
        "prompts": [{"name": "implement", "text": "Implement the plan."}],
        "nodes": [
            {"name": "load", "contract": "context"},
            {"name": "plan", "contract": "plan"},
            {
                "name": "implement",
                "contract": "implementation",
                "prompt": "implement",
            },
            {"name": "inspect", "contract": "review"},
            {"name": "verify", "contract": "review"},
            {"name": "close", "contract": "work_result"},
        ],
        "phases": [
            {"name": "prepare", "nodes": ["load", "plan"]},
            {"name": "build", "nodes": ["implement", "inspect"]},
            {"name": "finalize", "nodes": ["verify", "close"]},
        ],
        "ticket": {
            "ticket_type": "engineering.change",
            "input_contract": "work_request",
        },
    }

    declaration = _protocol_scaffold().ProtocolScaffoldDecl(**payload)

    assert declaration.graph_name == "dev.work.exec"
    assert len(declaration.contracts) == 6
    assert len(declaration.nodes) == 6
    assert len(declaration.prompts) == 1
    assert [len(phase.nodes) for phase in declaration.phases] == [2, 2, 2]
    assert declaration.ticket.ticket_type == "engineering.change"
    assert declaration.ticket.ticket_type != declaration.graph_name


def test_protocol_rejects_undeclared_component_references() -> None:
    """AC6: every well-formed unresolved component reference is identified."""
    cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        (
            "missing_contract",
            lambda data: data["nodes"][0].update(contract="missing_contract"),
        ),
        (
            "missing_prompt",
            lambda data: data["nodes"][0].update(prompt="missing_prompt"),
        ),
        (
            "missing_node",
            lambda data: data["phases"][0].update(nodes=["missing_node"]),
        ),
    )

    for reference, mutate in cases:
        payload = _valid_payload()
        mutate(payload)
        with pytest.raises(ValidationError) as caught:
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)
        assert reference in str(caught.value)


def test_optional_lists_do_not_weaken_ticket_contract_resolution() -> None:
    """AC7: omitted lists do not hide an unresolved ticket contract."""
    payload = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [{"name": "work_request"}],
        "nodes": [],
        "ticket": {
            "ticket_type": "dev.work",
            "input_contract": "missing_request",
        },
    }

    with pytest.raises(ValidationError) as caught:
        _protocol_scaffold().ProtocolScaffoldDecl(**payload)

    message = _validation_messages(caught.value)
    assert "missing_request" in message
    assert "prompts" not in message
    assert "phases" not in message


def test_optional_lists_do_not_make_ticket_linkage_optional() -> None:
    """AC8: a present ticket still requires its contract linkage."""
    payload = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [{"name": "work_request"}],
        "nodes": [],
        "ticket": {"ticket_type": "dev.work"},
    }

    with pytest.raises(ValidationError) as caught:
        _protocol_scaffold().ProtocolScaffoldDecl(**payload)

    message = _validation_messages(caught.value)
    assert "input_contract" in message
    assert "prompts" not in message
    assert "phases" not in message


def test_optional_node_references_do_not_allow_duplicate_component_names() -> None:
    """AC9: optional node references preserve uniqueness in every list."""
    duplicate_components = (
        ("contracts", [{"name": "same"}, {"name": "same"}]),
        ("prompts", [{"name": "same", "text": "a"}, {"name": "same", "text": "b"}]),
        ("nodes", [{"name": "same"}, {"name": "same"}]),
        ("phases", [{"name": "same"}, {"name": "same"}]),
    )

    for component, duplicates in duplicate_components:
        payload: dict[str, Any] = {
            "domain": "dev",
            "unit": "work",
            "action": "exec",
            "contracts": [],
            "nodes": [{"name": "optional_references"}],
        }
        payload[component] = duplicates
        with pytest.raises(ValidationError) as caught:
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)
        message = _validation_messages(caught.value)
        assert "component names must be unique" in message
        assert "Field required" not in message


def test_optional_node_references_do_not_allow_public_name_collisions() -> None:
    """AC10: optional node references preserve derived-name uniqueness."""
    payload = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [],
        "nodes": [{"name": "build"}],
        "phases": [{"name": "build"}],
    }

    with pytest.raises(ValidationError) as caught:
        _protocol_scaffold().ProtocolScaffoldDecl(**payload)

    message = _validation_messages(caught.value)
    assert "derived public names must be unique" in message
    assert "Field required" not in message


def test_optional_fields_do_not_allow_malformed_segments() -> None:
    """AC11: optional omissions never mask unsafe protocol-name segments."""
    for invalid_segment in ("dev/work", "..", "/dev", "class"):
        payload: dict[str, Any] = {
            "domain": invalid_segment,
            "unit": "work",
            "action": "exec",
            "contracts": [],
            "nodes": [],
        }

        with pytest.raises(ValidationError) as caught:
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)

        message = _validation_messages(caught.value)
        assert "('domain',) value_error" in message
        assert "Field required" not in message


def test_optional_fields_preserve_extra_forbid_on_every_model() -> None:
    """AC12: strict extra-field rejection survives every optional omission."""
    invalid_payloads = []

    contract = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [{"name": "request", "unexpected": True}],
        "nodes": [],
    }
    invalid_payloads.append(contract)

    prompt = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [],
        "nodes": [],
        "prompts": [{"name": "announce", "text": "Done", "unexpected": True}],
    }
    invalid_payloads.append(prompt)

    node = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [],
        "nodes": [{"name": "load", "unexpected": True}],
    }
    invalid_payloads.append(node)

    phase = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [],
        "nodes": [],
        "phases": [{"name": "build", "unexpected": True}],
    }
    invalid_payloads.append(phase)

    ticket = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [{"name": "request"}],
        "nodes": [],
        "ticket": {
            "ticket_type": "dev.work",
            "input_contract": "request",
            "unexpected": True,
        },
    }
    invalid_payloads.append(ticket)

    protocol = {
        "domain": "dev",
        "unit": "work",
        "action": "exec",
        "contracts": [],
        "nodes": [],
        "unexpected": True,
    }
    invalid_payloads.append(protocol)

    for payload in invalid_payloads:
        with pytest.raises(ValidationError) as caught:
            _protocol_scaffold().ProtocolScaffoldDecl(**payload)
        message = _validation_messages(caught.value)
        assert "extra_forbidden" in message
        assert "Field required" not in message
