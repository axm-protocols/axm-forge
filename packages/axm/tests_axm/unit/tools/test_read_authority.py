"""Service target reads preserve legacy behavior but honor bound authority."""

from __future__ import annotations

import json

import pytest

from axm import require_read_path, require_write_path
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract


def test_legacy_read_without_binding_or_ambient_contract_remains_allowed(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("AXM_WRITE_CONTRACT", raising=False)
    target = tmp_path / "legacy.db"
    require_read_path(target)
    with pytest.raises(PermissionError, match="write authority missing"):
        require_write_path(target)


def test_explicit_none_denies_read_and_suppresses_ambient_contract(
    tmp_path, monkeypatch
):
    target = tmp_path / "configured.db"
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(tmp_path),
                "read_roots": [str(target)],
            }
        ),
    )
    require_read_path(target)
    with dependency_read_context(None):
        with pytest.raises(PermissionError, match="read authority missing"):
            require_read_path(target)
    require_read_path(target)


def test_exact_configured_data_target_is_readable_without_granting_sibling_or_write(
    tmp_path,
):
    execution = tmp_path / "checkout"
    execution.mkdir()
    target = tmp_path / "authorized-profile.db"
    target.write_text("owned")
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(execution),
            "read_roots": [str(target)],
            "allowed_prefixes": [],
        }
    )
    with dependency_read_context(contract):
        require_read_path(target)
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path(tmp_path / "other-profile.db")
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path(execution / "local.db")
        with pytest.raises(PermissionError, match="outside write authority"):
            require_write_path(target)


@pytest.mark.parametrize("candidate", ["owned.db", "nested/../owned.db"])
def test_relative_read_uses_execution_root_not_ambient_cwd(
    tmp_path, monkeypatch, candidate
):
    execution = tmp_path / "owned"
    execution.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    contract = WriteContract.from_mapping({"execution_root": str(execution)})
    with dependency_read_context(contract):
        require_read_path(candidate)
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path("../outside.db")


def test_symlink_cannot_escape_readonly_root(tmp_path):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    outside = tmp_path / "secret.db"
    outside.write_text("not owned")
    (readonly / "escape.db").symlink_to(outside)
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path / "checkout"),
            "read_roots": [str(readonly)],
        }
    )
    with dependency_read_context(contract):
        require_read_path(readonly / "owned.db")
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path(readonly / "escape.db")


def test_nested_none_cannot_inherit_outer_authority(tmp_path):
    contract = WriteContract.from_mapping({"execution_root": str(tmp_path)})
    with dependency_read_context(contract):
        require_read_path(tmp_path / "owned.db")
        with dependency_read_context(None):
            with pytest.raises(PermissionError, match="read authority missing"):
                require_read_path(tmp_path / "owned.db")
        require_read_path(tmp_path / "owned.db")


def test_bound_read_roots_never_inherit_ambient_profile_or_dependency_roots(
    tmp_path, monkeypatch
):
    owned = tmp_path / "owned"
    owned.mkdir()
    ambient = tmp_path / "operator-profile.db"
    unrelated = tmp_path / "unrelated-package" / "data.db"
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(tmp_path),
                "read_roots": [str(ambient), str(unrelated.parent)],
            }
        ),
    )
    contract = WriteContract.from_mapping({"execution_root": str(owned)})
    with dependency_read_context(contract):
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path(ambient)
        with pytest.raises(PermissionError, match="outside read authority"):
            require_read_path(unrelated)
