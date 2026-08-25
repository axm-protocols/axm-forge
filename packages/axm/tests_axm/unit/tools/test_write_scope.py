from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm.tools.write_scope import (
    WRITE_CONTRACT_ENV,
    WriteContract,
    decide_write_access,
    write_contract_from_env,
)


def test_contract_normalizes_relative_prefixes(tmp_path: object) -> None:
    """Relative prefixes are resolved once against the execution root."""
    root = str(tmp_path)
    contract = WriteContract.from_mapping(
        {"execution_root": root, "allowed_prefixes": ["src", "src"]}
    )

    assert contract.allowed_prefixes == (f"{root}/src",)


@pytest.mark.parametrize(
    ("tool_name", "file", "allowed"),
    [
        ("batch_edit", "src/in.py", True),
        ("mcp__axm_mcp__batch_edit", "docs/out.py", False),
    ],
)
def test_batch_edit_scope_is_vendor_name_independent(
    tmp_path: object,
    tool_name: str,
    file: str,
    allowed: bool,
) -> None:
    """Direct MCP and vendor-prefixed spellings share one decision engine."""
    root = str(tmp_path)
    contract = WriteContract.from_mapping(
        {"execution_root": root, "allowed_prefixes": [f"{root}/src"]}
    )

    decision = decide_write_access(
        contract,
        tool_name,
        {
            "path": root,
            "operations": [{"op": "create", "file": file, "content": ""}],
        },
    )

    assert decision.allowed is allowed


def test_environment_transport_is_optional_and_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """Absence is permissive, while malformed presence fails closed."""
    monkeypatch.delenv(WRITE_CONTRACT_ENV, raising=False)
    assert write_contract_from_env() is None

    monkeypatch.setenv(
        WRITE_CONTRACT_ENV,
        json.dumps({"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}),
    )
    assert write_contract_from_env() is not None

    monkeypatch.setenv(WRITE_CONTRACT_ENV, "{bad-json")
    with pytest.raises(ValueError, match=WRITE_CONTRACT_ENV):
        write_contract_from_env()


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"execution_root": ""},
        {"execution_root": "/root", "allowed_prefixes": "src"},
        {"execution_root": "/root", "allowed_prefixes": [1]},
    ],
)
def test_contract_rejects_malformed_mappings(raw: dict[str, object]) -> None:
    """Every malformed wire shape is rejected instead of weakened."""
    with pytest.raises(ValueError):
        WriteContract.from_mapping(raw)


def test_contract_rejects_non_object_json() -> None:
    """The environment payload must be a JSON object."""
    with pytest.raises(ValueError, match="JSON object"):
        WriteContract.from_json("[]")


def test_contract_location_predicates_resolve_real_paths(tmp_path: Path) -> None:
    """Resolution, root containment and prefix permission share canonical paths."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )
    source = contract.resolve(contract.execution_root, "src/a.py")
    outside = contract.resolve(contract.execution_root, "docs/a.py")

    assert contract.contains(source) is True
    assert contract.permits(source) is True
    assert contract.contains(outside) is True
    assert contract.permits(outside) is False
    assert contract.contains(str(tmp_path.parent)) is False


def test_absent_contract_and_read_only_tool_are_allowed(tmp_path: Path) -> None:
    """No scope is inert, and a scope does not hide read-only AXM tools."""
    assert decide_write_access(None, "batch_edit", {}).allowed is True
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )
    decision = decide_write_access(contract, "ast_context", {"path": str(tmp_path)})

    assert decision.allowed is True
    assert "no filesystem mutation" in decision.reason


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "batch_edit", "arguments": []},
    ],
)
def test_malformed_facade_payload_fails_closed(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    """An active contract never guesses what a malformed facade call means."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )

    decision = decide_write_access(contract, "axm_call", payload)

    assert decision.allowed is False
    assert "facade input" in decision.reason


@pytest.mark.parametrize(
    "payload",
    [
        {"path": "/outside", "operations": []},
        {"path": ".", "operations": "not-a-sequence"},
        {"path": ".", "operations": ["not-a-mapping"]},
        {"path": ".", "operations": [{"op": "create"}]},
    ],
)
def test_batch_mutation_malformed_or_escaped_root_is_denied(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    """An escaped root and every unreadable batch shape fail closed."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )

    decision = decide_write_access(contract, "batch_edit", payload)

    assert decision.allowed is False


@pytest.mark.parametrize("tool_name", ["edit_file", "write_file"])
def test_direct_file_mutators_share_the_contract(
    tmp_path: Path,
    tool_name: str,
) -> None:
    """Single-file AXM mutators use the same root and target resolution."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )

    allowed = decide_write_access(
        contract,
        tool_name,
        {"path": str(tmp_path), "file": "src/a.py"},
    )
    denied = decide_write_access(
        contract,
        tool_name,
        {"path": str(tmp_path), "file": "docs/a.py"},
    )

    assert allowed.allowed is True
    assert denied.allowed is False


def test_unknown_operations_shape_is_denied(tmp_path: Path) -> None:
    """An unknown tool carrying mutation-like operations is never assumed safe."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["src"]}
    )

    decision = decide_write_access(
        contract,
        "future_mutator",
        {"operations": []},
    )

    assert decision.allowed is False
    assert "unclassifiable mutation" in decision.reason
