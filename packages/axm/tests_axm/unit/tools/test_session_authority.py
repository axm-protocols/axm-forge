"""Service authority: legacy local calls, bound calls and session ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm import (
    SessionGrant,
    authority_enforced,
    capture_session_grant,
    require_enforced_write_path,
    require_legacy_authority,
    require_session_access,
)
from axm.tools.dependency_reads import dependency_read_context, restricted_read_context
from axm.tools.write_scope import WriteContract

_ROOT = "/nonexistent-axm-session-authority"
_COPY = f"{_ROOT}/review/report.docx"
_ORIGINAL = f"{_ROOT}/originals/report.docx"
_SECRET = f"{_ROOT}/originals/secret.docx"


def _contract(*, reads: tuple[str, ...], writes: tuple[str, ...] = ()) -> WriteContract:
    return WriteContract.from_mapping(
        {
            "execution_root": _ROOT,
            "read_files": list(reads),
            "allowed_files": list(writes),
        }
    )


@pytest.fixture(autouse=True)
def _no_ambient_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXM_WRITE_CONTRACT", raising=False)


@pytest.fixture
def chat() -> WriteContract:
    return _contract(reads=(_ORIGINAL, _COPY), writes=(_COPY,))


def test_a_legacy_local_call_is_unrestricted() -> None:
    assert not authority_enforced()
    require_enforced_write_path("/anywhere/at/all.docx")
    require_legacy_authority("a preview server")
    grant = capture_session_grant()
    assert grant == SessionGrant(enforced=False)
    require_session_access(grant, Path("/anywhere/at/all.docx"))


def test_a_denial_binding_is_enforced() -> None:
    with dependency_read_context(None):
        assert authority_enforced()
        with pytest.raises(PermissionError):
            require_enforced_write_path(_COPY)
        with pytest.raises(PermissionError, match="preview"):
            require_legacy_authority("a preview server")
        with pytest.raises(PermissionError):
            capture_session_grant()


def test_reading_never_grants_writing(chat: WriteContract) -> None:
    with dependency_read_context(chat):
        require_enforced_write_path(_COPY)
        with pytest.raises(PermissionError):
            require_enforced_write_path(_ORIGINAL)


def test_a_session_belongs_to_its_exact_contract_even_with_a_shared_source(
    chat: WriteContract,
) -> None:
    """Memory may hold another file's content: reading the source is not enough."""
    wide = _contract(reads=(_ORIGINAL, _SECRET))
    narrow = _contract(reads=(_ORIGINAL,))
    with dependency_read_context(wide):
        grant = capture_session_grant()
        require_session_access(grant, Path(_ORIGINAL))
        require_session_access(grant, None)
    with dependency_read_context(narrow):
        with pytest.raises(PermissionError, match="another authority"):
            require_session_access(grant, Path(_ORIGINAL))
        with pytest.raises(PermissionError, match="another authority"):
            require_session_access(grant, None)
    with dependency_read_context(_contract(reads=(_ORIGINAL, _SECRET))):
        require_session_access(grant, Path(_ORIGINAL))
    require_session_access(grant, Path(_ORIGINAL))


def test_a_legacy_session_is_never_adopted_by_a_bound_call(chat: WriteContract) -> None:
    legacy = capture_session_grant()
    with dependency_read_context(chat):
        with pytest.raises(PermissionError, match="outside this authority"):
            require_session_access(legacy, Path(_ORIGINAL))
        with pytest.raises(PermissionError, match="outside this authority"):
            require_session_access(legacy, None)


def test_the_owner_still_needs_the_current_file(chat: WriteContract) -> None:
    with dependency_read_context(chat):
        grant = capture_session_grant()
        with pytest.raises(PermissionError):
            require_session_access(grant, Path(_SECRET))


def test_a_retained_origin_is_part_of_the_owner(chat: WriteContract) -> None:
    origin = _contract(reads=(_COPY,), writes=(_COPY,))
    with dependency_read_context(chat), restricted_read_context(origin):
        grant = capture_session_grant()
        require_session_access(grant, Path(_COPY))
    with dependency_read_context(chat):
        with pytest.raises(PermissionError, match="another authority"):
            require_session_access(grant, Path(_COPY))
