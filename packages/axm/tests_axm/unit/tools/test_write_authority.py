"""Persisted write authority is distinct from readable/dependency roots."""

from __future__ import annotations

import pytest

from axm import require_write_path
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract


def contract() -> WriteContract:
    return WriteContract.from_mapping(
        {
            "execution_root": "/tmp/axm-authority",
            "allowed_prefixes": ["writable"],
            "read_only_prefixes": ["readable"],
        }
    )


def test_missing_and_read_only_authority_are_refused(monkeypatch):
    monkeypatch.delenv("AXM_WRITE_CONTRACT", raising=False)
    with dependency_read_context(None):
        with pytest.raises(PermissionError, match="missing"):
            require_write_path("/tmp/axm-authority/writable/store.db")
    with dependency_read_context(contract()):
        require_write_path("/tmp/axm-authority/writable/store.db")
        with pytest.raises(PermissionError, match="outside"):
            require_write_path("/tmp/axm-authority/readable/store.db")
        with pytest.raises(PermissionError, match="outside"):
            require_write_path("/tmp/axm-authority/writable-other/store.db")


def test_relative_target_uses_execution_root_not_cwd():
    with dependency_read_context(contract()):
        require_write_path("writable/store.db")
        with pytest.raises(PermissionError):
            require_write_path("../outside/store.db")
