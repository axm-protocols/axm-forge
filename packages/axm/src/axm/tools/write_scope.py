from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

__all__ = [
    "WRITE_CONTRACT_ENV",
    "WriteAccessDecision",
    "WriteContract",
    "decide_write_access",
    "write_contract_from_env",
]

WRITE_CONTRACT_ENV = "AXM_WRITE_CONTRACT"
_AXM_PREFIX_ALIASES = (
    "mcp__axm-mcp__",
    "mcp__axm_mcp__",
    "axm-mcp__",
    "axm_mcp__",
)


class _MutationShape(NamedTuple):
    """How a mutation tool names its root, operation list and targets."""

    root_key: str
    operations_key: str | None
    target_key: str


_MUTATION_TOOLS: dict[str, _MutationShape] = {
    "batch_edit": _MutationShape("path", "operations", "file"),
    "edit_file": _MutationShape("path", None, "file"),
    "write_file": _MutationShape("path", None, "file"),
}


def _absolute_location(base: str, candidate: str) -> str:
    trimmed = candidate.strip()
    if os.path.isabs(trimmed):
        return os.path.realpath(trimmed)
    return os.path.realpath(os.path.join(base, trimmed))


@dataclass(frozen=True)
class WriteContract:
    """Validated wire representation of a session filesystem write scope."""

    execution_root: str
    allowed_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> WriteContract:
        """Validate and normalize a transported contract mapping."""
        raw_root = raw.get("execution_root")
        if not isinstance(raw_root, str) or not raw_root.strip():
            raise ValueError("execution_root must be a non-empty string")
        root = os.path.realpath(raw_root.strip())
        raw_prefixes = raw.get("allowed_prefixes", ())
        if isinstance(raw_prefixes, str) or not isinstance(raw_prefixes, Sequence):
            raise ValueError("allowed_prefixes must be a sequence of strings")
        if any(not isinstance(prefix, str) for prefix in raw_prefixes):
            raise ValueError("allowed_prefixes must contain only strings")
        prefixes = tuple(
            dict.fromkeys(
                _absolute_location(root, prefix)
                for prefix in raw_prefixes
                if isinstance(prefix, str)
            )
        )
        return cls(execution_root=root, allowed_prefixes=prefixes)

    @classmethod
    def from_json(cls, raw: str) -> WriteContract:
        """Decode, validate and normalize a JSON transport payload."""
        decoded = json.loads(raw)
        if not isinstance(decoded, Mapping):
            raise ValueError("write contract must be a JSON object")
        return cls.from_mapping(decoded)

    def resolve(self, base: str, candidate: str) -> str:
        """Resolve a candidate location relative to an explicit base."""
        return _absolute_location(base, candidate)

    def permits(self, location: str) -> bool:
        """Return whether a resolved location is under an allowed prefix."""
        return any(
            location == prefix or location.startswith(prefix + os.sep)
            for prefix in self.allowed_prefixes
        )

    def contains(self, location: str) -> bool:
        """Return whether a resolved location is under the execution root."""
        root = self.execution_root
        return location == root or location.startswith(root + os.sep)


@dataclass(frozen=True)
class WriteAccessDecision:
    """Verdict for one attempted filesystem mutation."""

    allowed: bool
    reason: str
    resolved_location: str | None = None
    consulted_prefixes: tuple[str, ...] = ()


def write_contract_from_env(
    env: Mapping[str, str] | None = None,
) -> WriteContract | None:
    """Load the optional process-scoped contract, failing closed if malformed."""
    source = os.environ if env is None else env
    raw = source.get(WRITE_CONTRACT_ENV)
    if raw is None:
        return None
    try:
        return WriteContract.from_json(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {WRITE_CONTRACT_ENV}: {exc}") from exc


def _canonical_tool_name(name: str) -> str:
    trimmed = name.strip()
    for prefix in _AXM_PREFIX_ALIASES:
        if trimmed.startswith(prefix):
            return trimmed[len(prefix) :]
    return trimmed


def _canonical_call(
    tool_name: str,
    tool_input: Mapping[str, object],
) -> tuple[str, Mapping[str, object], str | None]:
    canonical = _canonical_tool_name(tool_name)
    if canonical != "axm_call":
        return canonical, tool_input, None
    nested_name = tool_input.get("name")
    nested_arguments = tool_input.get("arguments")
    if not isinstance(nested_name, str):
        return canonical, tool_input, "malformed or unclassifiable AXM facade input"
    if nested_arguments is None:
        effective_arguments: Mapping[str, object] = {}
    elif isinstance(nested_arguments, Mapping):
        effective_arguments = nested_arguments
    else:
        return canonical, tool_input, "malformed or unclassifiable AXM facade input"
    return _canonical_tool_name(nested_name), effective_arguments, None


def _mutation_targets(
    shape: _MutationShape,
    tool_input: Mapping[str, object],
) -> list[str] | None:
    if shape.operations_key is None:
        target = tool_input.get(shape.target_key)
        if not isinstance(target, str) or not target.strip():
            return None
        return [target]
    raw_operations = tool_input.get(shape.operations_key)
    if isinstance(raw_operations, str) or not isinstance(raw_operations, Sequence):
        return None
    targets: list[str] = []
    for operation in raw_operations:
        if not isinstance(operation, Mapping):
            return None
        target = operation.get(shape.target_key)
        if not isinstance(target, str) or not target.strip():
            return None
        targets.append(target)
    return targets


def _denied(
    location: str,
    contract: WriteContract,
    detail: str,
) -> WriteAccessDecision:
    prefixes = ", ".join(contract.allowed_prefixes) or "<none>"
    return WriteAccessDecision(
        allowed=False,
        reason=f"{detail} {location} is outside the allowed prefixes ({prefixes})",
        resolved_location=location,
        consulted_prefixes=contract.allowed_prefixes,
    )


def _unclassified_tool_decision(
    canonical: str,
    payload: Mapping[str, object],
    contract: WriteContract,
) -> WriteAccessDecision:
    if "operations" in payload:
        return WriteAccessDecision(
            allowed=False,
            reason=f"malformed or unclassifiable mutation input for {canonical}",
            consulted_prefixes=contract.allowed_prefixes,
        )
    return WriteAccessDecision(
        allowed=True,
        reason=f"{canonical} declares no filesystem mutation",
        consulted_prefixes=contract.allowed_prefixes,
    )


def _decide_declared_mutation(
    tool_name: str,
    payload: Mapping[str, object],
    shape: _MutationShape,
    contract: WriteContract,
) -> WriteAccessDecision:
    raw_root = payload.get(shape.root_key, contract.execution_root)
    targets = _mutation_targets(shape, payload)
    if not isinstance(raw_root, str) or targets is None:
        return WriteAccessDecision(
            allowed=False,
            reason=f"malformed or unclassifiable mutation input for {tool_name}",
            consulted_prefixes=contract.allowed_prefixes,
        )
    root = contract.resolve(contract.execution_root, raw_root)
    if not contract.contains(root):
        return _denied(root, contract, f"{tool_name} project root")
    resolved = root
    for target in targets:
        resolved = contract.resolve(root, target)
        if not contract.permits(resolved):
            return _denied(resolved, contract, f"{tool_name} target")
    return WriteAccessDecision(
        allowed=True,
        reason=f"every {tool_name} target resolves inside the allowed prefixes",
        resolved_location=resolved,
        consulted_prefixes=contract.allowed_prefixes,
    )


def decide_write_access(
    contract: WriteContract | Mapping[str, object] | None,
    tool_name: str,
    tool_input: Mapping[str, object] | None = None,
) -> WriteAccessDecision:
    """Decide whether an AXM call may write where its payload requests."""
    if contract is None:
        return WriteAccessDecision(allowed=True, reason="no write contract is in force")
    resolved_contract = (
        contract
        if isinstance(contract, WriteContract)
        else WriteContract.from_mapping(contract)
    )
    payload: Mapping[str, object] = tool_input or {}
    canonical, payload, facade_error = _canonical_call(tool_name, payload)
    if facade_error is not None:
        return WriteAccessDecision(
            allowed=False,
            reason=facade_error,
            consulted_prefixes=resolved_contract.allowed_prefixes,
        )
    shape = _MUTATION_TOOLS.get(canonical)
    if shape is None:
        return _unclassified_tool_decision(canonical, payload, resolved_contract)
    return _decide_declared_mutation(
        canonical,
        payload,
        shape,
        resolved_contract,
    )
