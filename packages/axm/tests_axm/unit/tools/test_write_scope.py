from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm.tools.write_scope import (
    WRITE_CONTRACT_ENV,
    WriteContract,
    decide_write_access,
    restrict_write_contract,
    write_contract_from_env,
)


def test_contract_normalizes_relative_prefixes(tmp_path: object) -> None:
    """Relative prefixes are resolved once against the execution root."""
    root = str(tmp_path)
    contract = WriteContract.from_mapping(
        {"execution_root": root, "allowed_prefixes": ["src", "src"]}
    )

    assert contract.allowed_prefixes == (f"{root}/src",)


def test_intersection_keeps_live_metadata_but_never_unions_permissions():
    current = WriteContract(
        execution_root="/current",
        allowed_prefixes=("/data",),
        read_roots=("/data", "/only-current"),
    )
    origin = WriteContract(
        execution_root="/origin",
        allowed_prefixes=("/data/shared",),
        read_roots=("/data/shared", "/only-origin"),
    )
    intersection = restrict_write_contract(current, (origin,))
    assert intersection is not None
    assert intersection.execution_root == current.execution_root
    assert intersection.permits("/data/shared/record.db")
    assert intersection.readable("/data/shared/record.db")
    assert not intersection.permits("/data/private.db")
    assert not intersection.readable("/data/private.db")
    assert not intersection.readable("/only-current/record.db")
    assert not intersection.readable("/only-origin/record.db")


def test_intersection_preserves_markdown_nature_and_readonly_denial():
    current = WriteContract(execution_root="/owned", allowed_prefixes=("/owned",))
    markdown = WriteContract(
        execution_root="/owned",
        allowed_prefixes=("/owned",),
        markdown_only_prefixes=("/owned",),
    )
    intersection = restrict_write_contract(current, (markdown,))
    assert intersection is not None
    assert intersection.permits("/owned/note.md")
    assert not intersection.permits("/owned/data.db")
    readonly = WriteContract(execution_root="/owned")
    nested = restrict_write_contract(intersection, (readonly,))
    assert nested is not None
    assert nested.readable("/owned/note.md")
    assert not nested.permits("/owned/note.md")


def test_empty_restrictions_keep_legacy_contract_and_none_never_grants():
    current = WriteContract(execution_root="/owned", allowed_prefixes=("/owned",))
    assert restrict_write_contract(current, ()) is current
    assert restrict_write_contract(current, (None,)) is None
    assert restrict_write_contract(None, (current,)) is None


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


def test_markdown_only_prefix_grants_markdown_and_refuses_the_rest(
    tmp_path: Path,
) -> None:
    """A prefix carrying the Markdown nature grants sidecars, never code."""
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": ["docs"],
            "markdown_only_prefixes": ["docs"],
        }
    )

    assert contract.permits(str(tmp_path / "docs" / "index.md")) is True
    assert contract.permits(str(tmp_path / "docs" / "guide" / "deep.MD")) is True
    assert contract.permits(str(tmp_path / "docs" / "gen_ref_pages.py")) is False
    assert contract.permits(str(tmp_path / "docs" / "assets" / "logo.svg")) is False


def test_an_unrestricted_prefix_still_grants_a_location_it_covers(
    tmp_path: Path,
) -> None:
    """The nature narrows only what it alone grants, never a wider prefix."""
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": ["packages/a", "packages/a/src"],
            "markdown_only_prefixes": ["packages/a"],
        }
    )

    assert contract.permits(str(tmp_path / "packages/a/src/mod.py")) is True
    assert contract.permits(str(tmp_path / "packages/a/README.md")) is True
    assert contract.permits(str(tmp_path / "packages/a/pyproject.toml")) is False


def test_markdown_nature_is_dropped_when_the_prefix_is_not_allowed(
    tmp_path: Path,
) -> None:
    """A nature naming an ungranted prefix never widens the surface."""
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": ["docs"],
            "markdown_only_prefixes": ["packages/absent"],
        }
    )

    assert contract.markdown_only_prefixes == ()
    assert contract.permits(str(tmp_path / "packages/absent/x.md")) is False


def test_a_contract_without_the_nature_field_is_unchanged(tmp_path: Path) -> None:
    """Omitting the field keeps every historic grant, extension-blind."""
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_prefixes": ["docs"]}
    )

    assert contract.markdown_only_prefixes == ()
    assert contract.permits(str(tmp_path / "docs" / "gen_ref_pages.py")) is True


@pytest.mark.parametrize("malformed", ["docs", [1]])
def test_a_malformed_markdown_nature_is_rejected(
    tmp_path: Path, malformed: object
) -> None:
    """The nature sequence is validated like every other wire field."""
    with pytest.raises(ValueError, match="markdown_only_prefixes"):
        WriteContract.from_mapping(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": ["docs"],
                "markdown_only_prefixes": malformed,
            }
        )
