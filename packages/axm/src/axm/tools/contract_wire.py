"""Canonical, fail-closed transport for conjunctive filesystem authority."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from axm.tools.write_scope import WriteContract, restrict_write_contract

__all__ = ["contract_from_wire", "contract_leaves", "contract_to_wire"]

_VERSION = 2
_FIELDS = frozenset(
    {
        "execution_root",
        "allowed_prefixes",
        "markdown_only_prefixes",
        "read_roots",
        "read_files",
        "allowed_files",
        "read_path_aliases",
        "dependency_environment",
        "dependency_environments",
    }
)


def _leaf(contract: WriteContract) -> dict[str, object]:
    environment = contract.dependency_environment
    return {
        "execution_root": contract.execution_root,
        "allowed_prefixes": list(contract.allowed_prefixes),
        "markdown_only_prefixes": list(contract.markdown_only_prefixes),
        "read_roots": list(contract.read_roots),
        "read_files": list(contract.read_files),
        "allowed_files": list(contract.allowed_files),
        "read_path_aliases": [list(alias) for alias in contract.read_path_aliases],
        "dependency_environment": environment.to_mapping() if environment else None,
        "dependency_environments": [
            env.to_mapping() for env in contract.dependency_environments
        ],
    }


def contract_leaves(contract: WriteContract) -> tuple[WriteContract, ...]:
    """Return the ordered leaves of a retained conjunction."""
    leaves = [contract]
    for constraint in getattr(contract, "constraints", ()):
        leaves.extend(contract_leaves(constraint))
    return tuple(leaves)


def contract_to_wire(contract: WriteContract) -> str:
    """Encode all retained constraints, without flattening their authority."""
    return json.dumps(
        {
            "version": 2,
            "contracts": [_leaf(leaf) for leaf in contract_leaves(contract)],
        },
        separators=(",", ":"),
    )


def _parse_leaf(leaf: object) -> WriteContract:
    if not isinstance(leaf, Mapping) or set(leaf) != _FIELDS:
        raise ValueError("contract leaf must contain exactly the canonical fields")
    environments = leaf["dependency_environments"]
    if not isinstance(environments, (tuple, list)):
        raise ValueError("dependency_environments must be an array")
    for environment in (leaf["dependency_environment"], *environments):
        if environment is not None and (
            not isinstance(environment, Mapping)
            or set(environment) != {"interpreter", "package_root", "pythonpath"}
        ):
            raise ValueError("dependency environment has unknown or missing fields")
    return WriteContract.from_mapping(leaf)


def contract_from_wire(raw: str) -> WriteContract:
    """Decode a strict versioned conjunction, or the legacy single contract."""
    decoded = json.loads(raw)
    if not isinstance(decoded, Mapping):
        raise ValueError("write contract must be an object")
    if "version" not in decoded:
        return WriteContract.from_mapping(decoded)
    if (
        set(decoded) != {"version", "contracts"}
        or type(decoded["version"]) is not int
        or decoded["version"] != _VERSION
    ):
        raise ValueError("unsupported write contract envelope")
    leaves = decoded["contracts"]
    if (
        not isinstance(leaves, Sequence)
        or isinstance(leaves, (str, bytes))
        or not leaves
    ):
        raise ValueError("contracts must be a non-empty array")
    contracts = [_parse_leaf(leaf) for leaf in leaves]
    result = restrict_write_contract(contracts[0], tuple(contracts[1:]))
    if result is None:
        raise ValueError("invalid contract conjunction")
    return result
