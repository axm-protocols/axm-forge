"""Coexistence contracts for request ownership and lower-level adoption."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.framework import Framework
from axm_init.core.protocol_scaffolder import (
    ProtocolScaffoldRequest,
    prepare_protocol_request,
    preview_protocol_scaffold,
)
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl
from axm_init.tools.scaffold import InitScaffoldTool

IDENTITY = {
    "org": "test-org",
    "author": "Test Author",
    "email": "test@example.com",
}
DECLARATION: dict[str, object] = {
    "action": "create",
    "contracts": [],
    "nodes": [],
}


def _write_project(root: Path, *, name: str, owned_domain: str | None = None) -> None:
    root.mkdir()
    metadata = f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
    if owned_domain is not None:
        metadata += f'\n[tool.axm-init.protocols]\ndomain = "{owned_domain}"\n'
    (root / "pyproject.toml").write_text(metadata, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _direct_request() -> ProtocolScaffoldRequest:
    declaration = ProtocolScaffoldDecl.model_validate(
        {**DECLARATION, "domain": "dev", "unit": "work"}
    )
    return ProtocolScaffoldRequest(
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=(declaration,),
        preview=False,
    )


def _assert_direct_preview_adopts_profile(root: Path) -> None:
    result = preview_protocol_scaffold(root, _direct_request())

    assert result.success is True
    assert result.preview is False
    assert result.created
    assert all((root / relative).is_file() for relative in result.created)
    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.axm-init.protocols]" in metadata
    assert 'domain = "dev"' in metadata


@pytest.mark.integration
def test_missing_ownership_rejection_coexists_with_direct_preview(
    tmp_path: Path,
) -> None:
    """AC2: boundary rejection coexists with direct automatic profile adoption."""
    rejected_root = tmp_path / "unowned-request"
    _write_project(rejected_root, name="protocols-dev")
    before = _snapshot(rejected_root)

    rejected = InitScaffoldTool().execute(
        path=str(rejected_root),
        kind="protocol",
        profile=None,
        domain="dev",
        unit="work",
        protocols=[DECLARATION],
        preview=False,
        **IDENTITY,
    )

    assert rejected.success is False
    assert "profile" in (rejected.error or "").lower()
    assert _snapshot(rejected_root) == before

    direct_root = tmp_path / "direct-preview"
    _write_project(direct_root, name="protocols-dev")
    _assert_direct_preview_adopts_profile(direct_root)


@pytest.mark.integration
def test_domain_conflict_rejection_coexists_with_direct_preview(
    tmp_path: Path,
) -> None:
    """AC3: domain-conflict rejection coexists with direct automatic adoption."""
    rejected_root = tmp_path / "conflicting-request"
    _write_project(
        rejected_root,
        name="protocols-research",
        owned_domain="research",
    )
    before = _snapshot(rejected_root)

    prepared = prepare_protocol_request(
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[DECLARATION],
        preview=False,
        framework=Framework.PYTHON,
    )
    assert isinstance(prepared, ProtocolScaffoldRequest)
    rejected = InitScaffoldTool().execute(
        path=str(rejected_root),
        kind="protocol",
        profile=prepared.profile,
        domain=prepared.domain,
        unit=prepared.unit,
        protocols=[DECLARATION],
        preview=prepared.preview,
        **IDENTITY,
    )

    assert rejected.success is False
    assert "domain" in (rejected.error or "").lower()
    assert _snapshot(rejected_root) == before

    direct_root = tmp_path / "direct-preview"
    _write_project(direct_root, name="protocols-dev")
    _assert_direct_preview_adopts_profile(direct_root)
