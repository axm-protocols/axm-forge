from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import PurePosixPath

from tomlkit import parse
from tomlkit.items import Table

from axm_init.core.protocol_metadata import merge_protocol_metadata
from axm_init.models.protocol_scaffold import (
    ContractDecl,
    NodeDecl,
    PhaseDecl,
    PromptDecl,
    ProtocolScaffoldDecl,
    ProtocolUnitDecl,
    TicketDecl,
)

__all__ = [
    "PlanOperation",
    "PlanStatus",
    "ProtocolScaffoldPlan",
    "plan_protocol_scaffold",
    "plan_protocol_unit",
]

_SKELETON_MARKER = "# axm-init: incomplete-skeleton"
_ContentRenderer = Callable[[], str]


class PlanStatus(StrEnum):
    """Classify one planned relative-path operation."""

    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class PlanOperation:
    """Describe the non-mutating plan for one relative path."""

    path: PurePosixPath
    status: PlanStatus
    content: str | None


@dataclass(frozen=True, slots=True)
class ProtocolScaffoldPlan:
    """Hold ordered file operations and merged project metadata."""

    operations: tuple[PlanOperation, ...]
    metadata: str


@dataclass(frozen=True, slots=True)
class _PlannedFile:
    path: PurePosixPath
    render: _ContentRenderer


def _python_header() -> str:
    return "from __future__ import annotations\n"


def _render_initializer() -> str:
    return f"{_python_header()}\n__all__: list[str] = []\n"


def _render_contract(declaration: ContractDecl) -> str:
    return (
        f"{_python_header()}\n"
        "from pydantic import BaseModel\n\n"
        f'__all__ = ["{declaration.model_name}"]\n\n'
        f"{_SKELETON_MARKER}\n"
        f"class {declaration.model_name}(BaseModel):\n"
        '    """Incomplete generated protocol contract."""\n\n'
        "    pass\n"
    )


def _render_prompt(declaration: PromptDecl) -> str:
    return f"{_SKELETON_MARKER}\n\n{declaration.text}\n"


def _render_node(declaration: NodeDecl) -> str:
    return (
        f"{_python_header()}\n"
        f'__all__ = ["{declaration.factory_name}"]\n\n'
        f"{_SKELETON_MARKER}\n"
        f"def {declaration.factory_name}() -> None:\n"
        '    """Raise until the generated node is implemented."""\n'
        '    raise NotImplementedError("Scaffold: implementation required")\n'
    )


def _render_phase(declaration: PhaseDecl) -> str:
    return (
        f"{_python_header()}\n"
        f'__all__ = ["{declaration.factory_name}"]\n\n'
        f"{_SKELETON_MARKER}\n"
        f"def {declaration.factory_name}() -> None:\n"
        '    """Raise until the generated phase is implemented."""\n'
        '    raise NotImplementedError("Scaffold: implementation required")\n'
    )


def _render_shared_protocol(
    declaration: ProtocolScaffoldDecl, shared: ProtocolUnitDecl
) -> str:
    if (declaration.domain, declaration.unit, declaration.unit_ticket) != (
        shared.domain,
        shared.unit,
        shared.ticket.ticket_type,
    ):
        raise ValueError("unit_ticket must reference this domain/unit shared ticket")
    contract = next(
        item for item in shared.contracts if item.name == shared.ticket.input_contract
    )
    module = f"protocols_{shared.domain}.{shared.unit}"
    return (
        f"{_python_header()}\n"
        f"from {module}.contracts.{contract.name} import {contract.model_name}\n"
        f"from {module}.ticket import get_ticket_type\n\n"
        f"__all__ = [{contract.model_name!r}, 'get_ticket_type']\n\n"
        f"{_SKELETON_MARKER}\n"
        f"GRAPH_NAME = {declaration.graph_name!r}\n"
        f"UNIT_TICKET = {declaration.unit_ticket!r}\n"
    )


def _shared_profile_owned(metadata: str, declaration: ProtocolUnitDecl) -> bool:
    current: object = parse(metadata)
    for key in ("tool", "axm-init", "protocols"):
        if not isinstance(current, (dict, Table)):
            return False
        current = current.get(key)
    if not isinstance(current, Table):
        return False
    units = current.get("units", [])
    return any(
        item.get("name") == declaration.unit and "ticket_type" in item for item in units
    )


def plan_protocol_unit(
    declaration: ProtocolUnitDecl,
    metadata: str,
    inventory: Mapping[str, str],
) -> ProtocolScaffoldPlan:
    """Plan a single shared ticket and context without action-local copies."""
    from axm_init.core.protocol_unit import merge_protocol_unit

    root = f"src/protocols_{declaration.domain}/{declaration.unit}"
    model = next(
        item
        for item in declaration.contracts
        if item.name == declaration.ticket.input_contract
    )
    content = (
        f"{_python_header()}\n"
        "from protocols_core import TicketTypeDef\n"
        f"from protocols_{declaration.domain}.{declaration.unit}"
        f".contracts.{model.name} "
        f"import {model.model_name}\n\n"
        "__all__ = ['get_ticket_type']\n\n"
        f"TICKET_TYPE = {declaration.ticket.ticket_type!r}\n"
        f"INPUT_CONTRACT = {declaration.ticket.input_contract!r}\n"
        f"GRAPH_NAME = {declaration.graph_name!r}\n\n"
        "def get_ticket_type() -> TicketTypeDef:\n"
        '    """Return the single unit ticket definition."""\n'
        "    return TicketTypeDef(\n"
        f"        name=TICKET_TYPE, context_model={model.model_name},\n"
        "        graph=GRAPH_NAME,\n"
        "    )\n"
    )
    planned = [
        _fixed_file(
            f"src/protocols_{declaration.domain}/__init__.py", _render_initializer()
        ),
        _fixed_file(f"{root}/__init__.py", _render_initializer()),
        _fixed_file(f"{root}/contracts/__init__.py", _render_initializer()),
        _fixed_file(f"{root}/ticket.py", content),
        *[
            _fixed_file(f"{root}/contracts/{item.name}.py", _render_contract(item))
            for item in declaration.contracts
        ],
    ]
    owned = _shared_profile_owned(metadata, declaration)
    operations = tuple(
        _classify(
            item, inventory, profile_owned=owned or item.path.name == "__init__.py"
        )
        for item in sorted(planned, key=lambda item: item.path)
    )
    return ProtocolScaffoldPlan(
        operations=operations, metadata=merge_protocol_unit(metadata, declaration)
    )


def _render_protocol(declaration: ProtocolScaffoldDecl) -> str:
    return (
        f"{_python_header()}\n"
        f"{_SKELETON_MARKER}\n"
        f"GRAPH_NAME = {declaration.graph_name!r}\n"
    )


def _render_ticket(declaration: TicketDecl) -> str:
    return (
        f"{_python_header()}\n"
        f"{_SKELETON_MARKER}\n"
        f"TICKET_TYPE = {declaration.ticket_type!r}\n"
        f"INPUT_CONTRACT = {declaration.input_contract!r}\n"
    )


def _fixed_file(path: str, content: str) -> _PlannedFile:
    return _PlannedFile(PurePosixPath(path), lambda: content)


def _package_files(declaration: ProtocolScaffoldDecl) -> list[_PlannedFile]:
    root = f"src/protocols_{declaration.domain}"
    action = f"{root}/{declaration.unit}/{declaration.action}"
    package_paths = (
        f"{root}/__init__.py",
        f"{root}/{declaration.unit}/__init__.py",
        f"{action}/__init__.py",
        f"{action}/contracts/__init__.py",
        f"{action}/nodes/__init__.py",
        f"{action}/phases/__init__.py",
        f"{action}/prompts/__init__.py",
    )
    return [_fixed_file(path, _render_initializer()) for path in package_paths]


def _contract_files(
    declaration: ProtocolScaffoldDecl,
    action_root: str,
) -> list[_PlannedFile]:
    return [
        _PlannedFile(
            PurePosixPath(f"{action_root}/contracts/{contract.name}.py"),
            partial(_render_contract, contract),
        )
        for contract in declaration.contracts
    ]


def _node_files(
    declaration: ProtocolScaffoldDecl,
    action_root: str,
) -> list[_PlannedFile]:
    return [
        _PlannedFile(
            PurePosixPath(f"{action_root}/nodes/{node.name}.py"),
            partial(_render_node, node),
        )
        for node in declaration.nodes
    ]


def _prompt_files(
    declaration: ProtocolScaffoldDecl,
    action_root: str,
) -> list[_PlannedFile]:
    return [
        _PlannedFile(
            PurePosixPath(f"{action_root}/prompts/{prompt.name}.md"),
            partial(_render_prompt, prompt),
        )
        for prompt in declaration.prompts
    ]


def _phase_files(
    declaration: ProtocolScaffoldDecl,
    action_root: str,
) -> list[_PlannedFile]:
    return [
        _PlannedFile(
            PurePosixPath(f"{action_root}/phases/{phase.name}.py"),
            partial(_render_phase, phase),
        )
        for phase in declaration.phases
    ]


def _planned_files(declaration: ProtocolScaffoldDecl) -> tuple[_PlannedFile, ...]:
    unit_root = f"src/protocols_{declaration.domain}/{declaration.unit}"
    action_root = f"{unit_root}/{declaration.action}"
    files = [
        *_package_files(declaration),
        *_contract_files(declaration, action_root),
        *_node_files(declaration, action_root),
        *_prompt_files(declaration, action_root),
        *_phase_files(declaration, action_root),
        _PlannedFile(
            PurePosixPath(f"{action_root}/protocol.py"),
            lambda: _render_protocol(declaration),
        ),
    ]
    if declaration.ticket is not None:
        ticket = declaration.ticket
        files.append(
            _PlannedFile(
                PurePosixPath(f"{action_root}/ticket.py"),
                lambda: _render_ticket(ticket),
            )
        )
    return tuple(sorted(files, key=lambda planned: planned.path.as_posix()))


def _is_profile_owned(metadata: str, declaration: ProtocolScaffoldDecl) -> bool:
    document = parse(metadata)
    tool = document.get("tool")
    if not isinstance(tool, Table):
        return False
    axm_init = tool.get("axm-init")
    if not isinstance(axm_init, Table):
        return False
    profile = axm_init.get("protocols")
    return isinstance(profile, Table) and profile.get("domain") == declaration.domain


def _classify(
    planned: _PlannedFile,
    inventory: Mapping[str, str],
    *,
    profile_owned: bool,
) -> PlanOperation:
    relative_path = planned.path.as_posix()
    existing = inventory.get(relative_path)
    if existing is None:
        return PlanOperation(planned.path, PlanStatus.CREATE, planned.render())
    if not profile_owned:
        return PlanOperation(planned.path, PlanStatus.CONFLICT, None)
    if _SKELETON_MARKER not in existing:
        return PlanOperation(planned.path, PlanStatus.UNCHANGED, None)

    content = planned.render()
    if existing == content or existing.startswith(content):
        return PlanOperation(planned.path, PlanStatus.UNCHANGED, None)
    return PlanOperation(planned.path, PlanStatus.UPDATE, content)


def plan_protocol_scaffold(
    declaration: ProtocolScaffoldDecl,
    metadata: str,
    inventory: Mapping[str, str],
    *,
    unit_declaration: ProtocolUnitDecl | None = None,
) -> ProtocolScaffoldPlan:
    """Compute a deterministic scaffold plan without mutating caller state."""
    merged_metadata = merge_protocol_metadata(metadata, declaration)
    profile_owned = _is_profile_owned(metadata, declaration)
    operations = tuple(
        _classify(planned, inventory, profile_owned=profile_owned)
        for planned in _planned_files(declaration)
    )
    if declaration.unit_ticket is not None:
        if unit_declaration is None:
            raise ValueError("unit_ticket requires a resolved shared declaration")
        content = _render_shared_protocol(declaration, unit_declaration)
        path = PurePosixPath(
            f"src/protocols_{declaration.domain}/{declaration.unit}/{declaration.action}/protocol.py"
        )
        operations = tuple(
            _classify(
                _fixed_file(str(path), content), inventory, profile_owned=profile_owned
            )
            if item.path == path
            else item
            for item in operations
        )
    return ProtocolScaffoldPlan(operations=operations, metadata=merged_metadata)
