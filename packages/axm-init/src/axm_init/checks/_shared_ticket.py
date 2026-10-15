"""Static checks of shared unit bindings; never import generated modules."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from axm_init.models.protocol_scaffold import ContractDecl, ProtocolUnitDecl

__all__ = ["shared_ticket_findings"]


def _tree(path: Path, findings: list[str]) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        findings.append(f"{path}: shared ticket resource is unreadable: {exc}")
        return None


def _imports(tree: ast.Module) -> dict[str, str]:
    return {
        alias.asname or alias.name: f"{node.module}.{alias.name}"
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def _literal(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            try:
                return ast.literal_eval(node.value)
            except (ValueError, TypeError):
                return None
    return None


def _context_target(declaration: ProtocolUnitDecl, model: ContractDecl) -> str:
    module = f"protocols_{declaration.domain}.{declaration.unit}"
    return f"{module}.contracts.{model.name}.{model.model_name}"


def _factory_call(tree: ast.Module) -> ast.Call | None:
    factory = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "get_ticket_type"
        ),
        None,
    )
    returns = (
        []
        if factory is None
        else [node.value for node in ast.walk(factory) if isinstance(node, ast.Return)]
    )
    if len(returns) != 1 or not isinstance(returns[0], ast.Call):
        return None
    return returns[0]


def _valid_factory(
    call: ast.Call | None, bindings: dict[str, str], context: str
) -> bool:
    if call is None or not isinstance(call.func, ast.Name):
        return False
    if bindings.get(call.func.id) != "protocols_core.TicketTypeDef":
        return False
    arguments = {item.arg: item.value for item in call.keywords}
    names = {
        name: value.id
        for name, value in arguments.items()
        if isinstance(value, ast.Name)
    }
    return (
        names.get("name") == "TICKET_TYPE"
        and names.get("graph") == "GRAPH_NAME"
        and bindings.get(names.get("context_model", "")) == context
        and not call.args
    )


def _factory_findings(
    declaration: ProtocolUnitDecl, tree: ast.Module, path: Path
) -> list[str]:
    findings: list[str] = []
    model = next(
        item
        for item in declaration.contracts
        if item.name == declaration.ticket.input_contract
    )
    expected = {
        "TICKET_TYPE": declaration.ticket.ticket_type,
        "INPUT_CONTRACT": model.name,
        "GRAPH_NAME": declaration.graph_name,
    }
    if any(_literal(tree, name) != value for name, value in expected.items()):
        findings.append(
            f"{path}: shared ticket constants disagree with its declaration"
        )
    if not _valid_factory(
        _factory_call(tree), _imports(tree), _context_target(declaration, model)
    ):
        findings.append(
            f"{path}: get_ticket_type must return the declared TicketTypeDef"
        )
    return findings


def _declaration(domain: str, unit: dict[str, object]) -> ProtocolUnitDecl | None:
    if not {"ticket_type", "input_contract", "entry_action"} & unit.keys():
        return None
    contracts = unit.get("contracts")
    if not isinstance(contracts, list):
        raise ValueError("shared contracts must be a list")
    return ProtocolUnitDecl.model_validate(
        {
            "domain": domain,
            "unit": unit.get("name"),
            "contracts": [{"name": item} for item in contracts],
            "ticket": {
                "ticket_type": unit.get("ticket_type"),
                "input_contract": unit.get("input_contract"),
                "entry_action": unit.get("entry_action"),
            },
        }
    )


def _actions(unit: dict[str, object]) -> list[dict[str, object]]:
    raw = unit.get("protocols", [])
    if not isinstance(raw, list):
        return []
    return [cast("dict[str, object]", item) for item in raw if isinstance(item, dict)]


def _consumers(actions: list[dict[str, object]]) -> list[dict[str, object]]:
    return [action for action in actions if action.get("unit_ticket") is not None]


def _metadata_findings(
    declaration: ProtocolUnitDecl | None,
    actions: list[dict[str, object]],
    identities: set[str],
) -> list[str]:
    consumers = _consumers(actions)
    if declaration is None:
        return [] if not consumers else ["pyproject.toml: unresolved unit_ticket"]
    identity = declaration.ticket.ticket_type
    findings = []
    if identity in identities:
        findings.append(
            f"pyproject.toml: shared ticket_type {identity!r} is duplicated"
        )
    identities.add(identity)
    for consumer in consumers:
        if consumer.get("unit_ticket") != identity or consumer.get("ticket_type"):
            findings.append(
                "pyproject.toml: unit_ticket must reference this unit exclusively"
            )
    return findings


def shared_ticket_findings(
    project: Path,
    domain: str,
    units: list[dict[str, object]],
    entry_points: dict[str, dict[str, object]],
) -> list[str]:
    """Validate unit ownership, consumers and publication against its entry action."""
    findings: list[str] = []
    identities: set[str] = set()
    for unit in units:
        try:
            declaration = _declaration(domain, unit)
        except ValueError as exc:
            findings.append(f"pyproject.toml: invalid shared unit: {exc}")
            continue
        actions = _actions(unit)
        findings.extend(_metadata_findings(declaration, actions, identities))
        if declaration is not None:
            findings.extend(_unit_findings(project, declaration, actions, entry_points))
    local_types = {
        action.get("ticket_type") for unit in units for action in _actions(unit)
    }
    if identities & local_types:
        findings.append(
            "pyproject.toml: local ticket conflicts with shared ticket type"
        )
    return findings


def _consumer_findings(
    root: Path, declaration: ProtocolUnitDecl, consumer: dict[str, object]
) -> list[str]:
    findings: list[str] = []
    path = root / str(consumer.get("action")) / "protocol.py"
    tree = _tree(path, findings)
    if tree is None:
        return findings
    bindings = set(_imports(tree).values())
    model = next(
        item
        for item in declaration.contracts
        if item.name == declaration.ticket.input_contract
    )
    module = f"protocols_{declaration.domain}.{declaration.unit}"
    expected = {f"{module}.ticket.get_ticket_type", _context_target(declaration, model)}
    if not expected <= bindings:
        findings.append(f"{path}: explicitly import the unit ticket and shared context")
    if _literal(tree, "UNIT_TICKET") != declaration.ticket.ticket_type:
        findings.append(f"{path}: UNIT_TICKET must match the explicit shared reference")
    return findings


def _context_findings(path: Path, contract: ContractDecl) -> list[str]:
    findings: list[str] = []
    tree = _tree(path, findings)
    if tree is None:
        return findings
    bindings = _imports(tree)
    model = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == contract.model_name
        ),
        None,
    )
    bases = [] if model is None else model.bases
    if not any(
        isinstance(base, ast.Name) and bindings.get(base.id) == "pydantic.BaseModel"
        for base in bases
    ):
        findings.append(
            f"{path}: shared context must declare {contract.model_name}(BaseModel)"
        )
    return findings


def _unit_findings(
    project: Path,
    declaration: ProtocolUnitDecl,
    actions: list[dict[str, object]],
    entry_points: dict[str, dict[str, object]],
) -> list[str]:
    root = project / "src" / f"protocols_{declaration.domain}" / declaration.unit
    findings = [
        finding
        for consumer in _consumers(actions)
        for finding in _consumer_findings(root, declaration, consumer)
    ]
    ticket = root / "ticket.py"
    tree = _tree(ticket, findings)
    if tree is not None:
        findings.extend(_factory_findings(declaration, tree, ticket))
    for contract in declaration.contracts:
        findings.extend(
            _context_findings(root / "contracts" / f"{contract.name}.py", contract)
        )
    entry = next(
        (
            item
            for item in actions
            if item.get("action") == declaration.ticket.entry_action
        ),
        None,
    )
    if entry is None:
        findings.append("pyproject.toml: shared ticket entry_action is not declared")
    findings.extend(_registration_findings(declaration, entry, entry_points))
    return findings


def _registration_claims(
    groups: dict[str, dict[str, object]], identity: str, target: str
) -> list[tuple[str, str, object]]:
    return [
        (group, key, value)
        for group, entries in groups.items()
        for key, value in entries.items()
        if key == identity or value == target
    ]


def _registration_findings(
    declaration: ProtocolUnitDecl,
    entry: dict[str, object] | None,
    groups: dict[str, dict[str, object]],
) -> list[str]:
    identity = declaration.ticket.ticket_type
    module = f"protocols_{declaration.domain}.{declaration.unit}"
    target = f"{module}.ticket:get_ticket_type"
    claims = _registration_claims(groups, identity, target)
    expected = [("axm.tribunal.ticket_types", identity, target)]
    ready = entry is not None and entry.get("state") == "ready"
    if claims and (not ready or claims != expected):
        return [
            "pyproject.toml: shared ticket registration must be unique "
            "and its entry graph ready"
        ]
    graph_target = f"{module}.{declaration.ticket.entry_action}.protocol:build_protocol"
    graph = groups.get("axm.tribunal.graphs", {}).get(declaration.graph_name)
    if ready and (claims != expected or graph != graph_target):
        return [
            "pyproject.toml: ready shared ticket requires its unit factory "
            "and Tribunal entry graph"
        ]
    return []
