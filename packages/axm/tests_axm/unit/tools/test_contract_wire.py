"""Conjunctive filesystem contract transport."""

import json
from pathlib import Path

import pytest

from axm.tools.contract_wire import contract_from_wire, contract_to_wire
from axm.tools.write_scope import WriteContract, restrict_write_contract


def test_public_contract_and_operator_ports_are_reexported() -> None:
    import axm
    import axm.tools

    assert (
        Path(axm.__file__)
        .resolve()
        .is_relative_to(Path(__file__).resolve().parents[3] / "src")
    )
    names = (
        "contract_from_wire",
        "contract_leaves",
        "contract_to_wire",
        "operator_authorized",
    )
    for name in names:
        assert name in axm.__all__
        assert name in axm.tools.__all__
        assert getattr(axm, name) is getattr(axm.tools, name)
    assert axm.operator_authorized("unknown-tool") is False


def test_conjunction_round_trip_enforces_each_leaf(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    one = tmp_path / "one.txt"
    two = child / "two.md"
    one.write_text("1")
    two.write_text("2")
    parent = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [str(tmp_path)],
            "read_roots": [str(tmp_path)],
        }
    )
    narrow = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [str(child)],
            "markdown_only_prefixes": [str(child)],
            "read_files": [str(two)],
        }
    )
    combined = restrict_write_contract(parent, (narrow,))
    assert combined is not None
    combined = restrict_write_contract(combined, (parent,))
    assert combined is not None
    wire = contract_to_wire(combined)
    decoded = contract_from_wire(wire)
    assert decoded.permits(str(two))
    assert not decoded.permits(str(child / "bad.py"))
    assert not decoded.readable(str(one))
    assert decoded.readable(str(two))
    with pytest.raises(ValueError):
        WriteContract.from_json(wire)
    payload = json.loads(wire)
    payload["contracts"][0]["unknown"] = 1
    with pytest.raises(ValueError):
        contract_from_wire(json.dumps(payload))


def test_symlink_cannot_escape_conjunction(tmp_path: Path) -> None:
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (inside / "link").symlink_to(outside, target_is_directory=True)
    leaf = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [str(inside)],
            "read_roots": [str(inside)],
        }
    )
    decoded = contract_from_wire(contract_to_wire(leaf))
    assert not decoded.permits(str(inside / "link" / "escape.md"))
    assert not decoded.readable(str(inside / "link" / "escape.md"))


def test_runtime_must_be_allowed_by_every_leaf(tmp_path: Path) -> None:
    from axm.tools.dependency_reads import (
        dependency_read_context,
        session_dependency_environment,
    )

    interpreter = tmp_path / "python"
    interpreter.touch()
    environment = {
        "interpreter": str(interpreter),
        "package_root": str(tmp_path),
        "pythonpath": [],
    }
    parent = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "dependency_environment": environment,
        }
    )
    denied = WriteContract.from_mapping({"execution_root": str(tmp_path)})
    restricted = restrict_write_contract(parent, (denied,))
    assert restricted is not None
    with dependency_read_context(restricted):
        with pytest.raises(ValueError, match="every contract"):
            session_dependency_environment(tmp_path)
    granted = restrict_write_contract(parent, (parent,))
    assert granted is not None
    with dependency_read_context(granted):
        assert session_dependency_environment(tmp_path) == parent.dependency_environment


def test_dependency_lookup_respects_read_conjunction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from axm.tools import dependency_reads
    from axm.tools.dependency_reads import DependencySources, dependency_read_context

    package = tmp_path / "pkg"
    package.mkdir()
    source = package / "module.py"
    source.write_text("value = 1")
    environment = {
        "interpreter": str(tmp_path / "python"),
        "package_root": str(tmp_path),
        "pythonpath": [str(tmp_path)],
    }
    parent = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "dependency_environment": environment,
        }
    )
    narrow = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "read_roots": [str(tmp_path / "elsewhere")],
        }
    )
    combined = restrict_write_contract(parent, (narrow,))
    assert combined is not None
    monkeypatch.setattr(
        dependency_reads,
        "dependency_sources",
        lambda _env: DependencySources((("pkg", str(package)),)),
    )
    with dependency_read_context(combined):
        assert (
            dependency_reads.session_dependencies().resolve_symbol("pkg.module") is None
        )
