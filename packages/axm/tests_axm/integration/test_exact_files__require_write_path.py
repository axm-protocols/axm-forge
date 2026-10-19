"""Exact document authority survives creation without granting a directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

import pytest

from axm import require_read_path, require_write_path
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract, restrict_write_contract

pytestmark = pytest.mark.integration


def test_exact_files_survive_creation_and_do_not_grant_neighbors(tmp_path):
    original = tmp_path / "original.docx"
    original.write_bytes(b"original")
    draft = tmp_path / "private" / "copy.docx"
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path / "package"),
            "read_files": [str(original), str(draft)],
            "allowed_files": [str(draft)],
        }
    )
    restored = WriteContract.from_json(json.dumps(asdict(contract)))
    with dependency_read_context(restored):
        require_read_path(original)
        require_write_path(draft)
        draft.parent.mkdir()
        draft.write_bytes(b"proposal")
        require_read_path(draft)
        require_write_path(draft)
        for refused in [
            original,
            draft.parent,
            draft.parent / "base.bin",
            draft / "child",
        ]:
            with pytest.raises(PermissionError):
                require_write_path(refused)
        with pytest.raises(PermissionError):
            require_read_path(draft.parent / "other.docx")
    assert original.read_bytes() == b"original"


@pytest.mark.parametrize("kind", ["directory", "symlink", "hardlink", "fifo"])
def test_exact_write_target_cannot_be_replaced_with_other_object(tmp_path, kind):
    target = tmp_path / "draft.docx"
    protected = tmp_path / "original.docx"
    protected.write_bytes(b"untouched")
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_files": [str(target)]}
    )
    if kind == "directory":
        target.mkdir()
    elif kind == "symlink":
        target.symlink_to(protected)
    elif kind == "hardlink":
        os.link(protected, target)
    else:
        os.mkfifo(target)
    with dependency_read_context(contract), pytest.raises(PermissionError):
        require_write_path(target)
    assert protected.read_bytes() == b"untouched"


def test_exact_read_target_does_not_become_directory_authority(tmp_path):
    target = tmp_path / "document"
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path / "package"), "read_files": [str(target)]}
    )
    target.mkdir()
    (target / "secret").write_bytes(b"secret")
    with dependency_read_context(contract):
        for refused in [target, target / "secret"]:
            with pytest.raises(PermissionError):
                require_read_path(refused)


def test_retained_authority_intersects_exact_files(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    old = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_files": [str(first)]}
    )
    live = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_files": [str(first), str(second)]}
    )
    restricted = restrict_write_contract(live, (old,))
    with dependency_read_context(restricted):
        require_write_path(first)
        with pytest.raises(PermissionError):
            require_write_path(second)


@pytest.mark.parametrize("field", ["read_files", "allowed_files"])
@pytest.mark.parametrize("value", ["a.docx", [1], None])
def test_exact_file_wire_fields_fail_closed(tmp_path, field, value):
    with pytest.raises(ValueError):
        WriteContract.from_mapping({"execution_root": str(tmp_path), field: value})


@pytest.mark.parametrize("suffix", ["", " "])
def test_whitespace_is_part_of_exact_filename(tmp_path, suffix):
    granted = tmp_path / f"document.docx{suffix}"
    neighbor = tmp_path / f"document.docx{' ' if not suffix else ''}"
    granted.write_bytes(b"granted")
    neighbor.write_bytes(b"private")
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path / "package"),
            "read_files": [str(granted)],
            "allowed_files": [str(granted)],
        }
    )
    with dependency_read_context(contract):
        require_read_path(granted)
        require_write_path(granted)
        for guard in [require_read_path, require_write_path]:
            with pytest.raises(PermissionError):
                guard(neighbor)


def test_retained_contract_cannot_roundtrip_into_wider_authority(tmp_path):
    old = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "allowed_files": [str(tmp_path / "a")]}
    )
    live = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_files": [str(tmp_path / "a"), str(tmp_path / "b")],
        }
    )
    restricted = restrict_write_contract(live, (old,))
    assert restricted is not None
    with pytest.raises(ValueError, match="retained authority"):
        WriteContract.from_json(json.dumps(asdict(restricted)))


@pytest.mark.parametrize("field", ["read_files", "allowed_files"])
@pytest.mark.parametrize("ancestor", [False, True])
def test_transported_exact_grants_never_follow_replaced_links(
    tmp_path, field, ancestor
):
    directory = tmp_path / "admitted"
    directory.mkdir()
    target = directory / "document.docx"
    other = tmp_path / "other"
    other.mkdir()
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path / "package"), field: [str(target)]}
    )
    header = json.dumps(asdict(contract))
    if ancestor:
        directory.rmdir()
        directory.symlink_to(other, target_is_directory=True)
    else:
        target.symlink_to(other / "document.docx")
    assert not contract.permits(str(target))
    assert not contract.readable(str(target))
    with pytest.raises(ValueError, match="canonical absolute"):
        WriteContract.from_json(header)


def test_exact_files_do_not_inherit_implicit_execution_root_reads(tmp_path):
    document = tmp_path / "document.docx"
    private = tmp_path / "secret"
    contract = WriteContract.from_mapping(
        {"execution_root": str(tmp_path), "read_files": [str(document)]}
    )
    with dependency_read_context(contract):
        require_read_path(document)
        with pytest.raises(PermissionError):
            require_read_path(private)
