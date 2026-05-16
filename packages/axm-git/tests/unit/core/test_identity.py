"""Unit test for resolve_identity: no-config-file edge case."""

from __future__ import annotations

import inspect as _inspect_axm1710
from pathlib import Path
from typing import Any

import axm_git.core.identity as _ident_axm1710
from axm_git.core.identity import (
    GitIdentity,
    GitProfileConfig,
    author_args,
    resolve_identity,
)


class TestResolveIdentityEdgeCases:
    def test_no_config_file_returns_none(self, monkeypatch):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: None)
        result = resolve_identity(Path("/any"))
        assert result is None


def _build_config_axm1710(
    *,
    workspace_paths: list[Path] | None = None,
    timezone: str | None = None,
    schedule_rules: list[dict[str, Any]] | None = None,
    profiles: dict[str, dict[str, str]] | None = None,
) -> GitProfileConfig:
    payload: dict[str, Any] = {
        "default": {"name": "Default", "email": "default@example.com"},
        "profiles": profiles or {},
        "schedule": {"rules": schedule_rules or []},
    }
    if workspace_paths is not None:
        payload["workspace_paths"] = [str(p) for p in workspace_paths]
    if timezone is not None:
        payload["timezone"] = timezone
    return GitProfileConfig.model_validate(payload)


class TestGitIdentityModel:
    """Test GitIdentity pydantic model."""

    def test_git_identity_model(self) -> None:
        identity = GitIdentity(name="Axiom", email="axiom@axm-protocol.io")
        assert identity.name == "Axiom"
        assert identity.email == "axiom@axm-protocol.io"


class TestAuthorArgs:
    """Test author_args helper."""

    def test_author_args_with_identity(self) -> None:
        identity = GitIdentity(name="Axiom", email="axiom@axm-protocol.io")
        result = author_args(identity)
        assert result == ["--author", "Axiom <axiom@axm-protocol.io>"]

    def test_author_args_none(self) -> None:
        result = author_args(None)
        assert result == []


class TestIdentityModuleInvariants:
    """Unit-scope invariants on the identity module (no I/O)."""

    def test_no_hardcoded_workspace_prefix_in_module(self) -> None:
        src = _inspect_axm1710.getsource(_ident_axm1710)
        assert "/Users/" not in src
        assert "_AXM_WORKSPACE_PREFIX" not in src

    def test_resolve_identity_default_timezone_is_europe_paris(self) -> None:
        config = _build_config_axm1710()
        assert config.timezone == "Europe/Paris"
