from __future__ import annotations

import keyword
from pathlib import PurePath
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "ContractDecl",
    "NodeDecl",
    "PhaseDecl",
    "PromptDecl",
    "ProtocolScaffoldDecl",
    "TicketDecl",
]


def _validate_segment(value: str) -> str:
    if (
        not value.isidentifier()
        or not value.islower()
        or keyword.iskeyword(value)
        or value in {".", ".."}
        or PurePath(value).is_absolute()
        or "/" in value
        or "\\" in value
    ):
        msg = "must be a safe lowercase Python identifier"
        raise ValueError(msg)
    return value


def _validate_qualified_name(value: str) -> str:
    parts = value.split(".")
    if not parts or any(not part for part in parts):
        msg = "must contain valid lowercase Python identifier segments"
        raise ValueError(msg)
    for part in parts:
        _validate_segment(part)
    return value


type Segment = Annotated[str, AfterValidator(_validate_segment)]
type QualifiedName = Annotated[str, AfterValidator(_validate_qualified_name)]


def _pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


class _StrictDecl(BaseModel):  # type: ignore[explicit-any]
    model_config = ConfigDict(extra="forbid")


class ContractDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Declare a named data contract used by a protocol component."""

    name: Segment

    @property
    def model_name(self) -> str:
        return _pascal_case(self.name)


class PromptDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Declare a named prompt and its text."""

    name: Segment
    text: str


class NodeDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Declare a node with optional contract and prompt references."""

    name: Segment
    contract: Segment | None = None
    prompt: Segment | None = None

    @property
    def factory_name(self) -> str:
        return f"build_{self.name}"


class PhaseDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Declare a phase and the nodes it contains, if any."""

    name: Segment
    nodes: list[Segment] = Field(default_factory=list)

    @property
    def factory_name(self) -> str:
        return f"build_{self.name}"


class TicketDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Bind a ticket type to one declared input contract."""

    ticket_type: QualifiedName
    input_contract: Segment


class ProtocolScaffoldDecl(_StrictDecl):  # type: ignore[explicit-any]
    """Validate a complete protocol declaration and its component references."""

    domain: Segment
    unit: Segment
    action: Segment
    contracts: list[ContractDecl]
    nodes: list[NodeDecl]
    prompts: list[PromptDecl] = Field(default_factory=list)
    phases: list[PhaseDecl] = Field(default_factory=list)
    ticket: TicketDecl | None = None

    @property
    def graph_name(self) -> str:
        return ".".join((self.domain, self.unit, self.action))

    @model_validator(mode="after")
    def _validate_declaration(self) -> Self:
        self._reject_duplicate_components()
        self._reject_public_name_collisions()
        self._validate_component_references()
        self._validate_ticket_binding()
        return self

    def _reject_duplicate_components(self) -> None:
        for components in (self.contracts, self.nodes, self.prompts, self.phases):
            names = [component.name for component in components]
            if len(names) != len(set(names)):
                msg = "component names must be unique within each component list"
                raise ValueError(msg)

    def _reject_public_name_collisions(self) -> None:
        public_names = [
            *(contract.model_name for contract in self.contracts),
            *(node.factory_name for node in self.nodes),
            *(phase.factory_name for phase in self.phases),
        ]
        if len(public_names) != len(set(public_names)):
            msg = "derived public names must be unique"
            raise ValueError(msg)

    def _validate_component_references(self) -> None:
        declared_contracts = {contract.name for contract in self.contracts}
        declared_prompts = {prompt.name for prompt in self.prompts}
        declared_nodes = {node.name for node in self.nodes}

        for node in self.nodes:
            if node.contract is not None and node.contract not in declared_contracts:
                msg = (
                    f"node contract {node.contract!r} must reference "
                    "a declared contract"
                )
                raise ValueError(msg)
            if node.prompt is not None and node.prompt not in declared_prompts:
                msg = f"node prompt {node.prompt!r} must reference a declared prompt"
                raise ValueError(msg)

        for phase in self.phases:
            for node_reference in phase.nodes:
                if node_reference not in declared_nodes:
                    msg = (
                        f"phase node {node_reference!r} must reference a declared node"
                    )
                    raise ValueError(msg)

    def _validate_ticket_binding(self) -> None:
        if self.ticket is None:
            return
        declared_contracts = {contract.name for contract in self.contracts}
        if self.ticket.input_contract not in declared_contracts:
            msg = (
                f"ticket input_contract {self.ticket.input_contract!r} "
                "must reference a declared contract"
            )
            raise ValueError(msg)
