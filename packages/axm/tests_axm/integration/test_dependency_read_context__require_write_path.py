"""Symlink targets cannot escape a persisted write authority."""

from __future__ import annotations

import pytest

from axm import require_write_path
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract

pytestmark = pytest.mark.integration


def test_symlink_into_read_only_store_is_refused(tmp_path):
    writable = tmp_path / "writable"
    writable.mkdir()
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    (writable / "alias").symlink_to(readonly, target_is_directory=True)
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": ["writable"],
            "read_only_prefixes": ["readonly"],
        }
    )
    with dependency_read_context(contract):
        require_write_path(writable / "store.db")
        with pytest.raises(PermissionError):
            require_write_path(writable / "alias" / "store.db")
