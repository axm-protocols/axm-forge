"""Unit tests for the shared scaffolding seam (``core.scaffolder``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from axm_init.core.scaffolder import build_member_data, resolve_workspace_root

_SCAFFOLD_DATA = {
    "org": "acme",
    "author_name": "Ada",
    "author_email": "ada@example.com",
    "license": "Apache-2.0",
    "description": "A demo member",
}


class TestBuildMemberData:
    """AC1/AC2 — the one builder is the single source of truth."""

    def test_cli_and_mcp_shaped_inputs_produce_same_payload(self) -> None:
        """CLI-shaped and MCP-shaped inputs yield one canonical payload."""
        cli_shaped = {
            "org": "acme",
            "author_name": "Ada",
            "author_email": "ada@example.com",
            "license": "Apache-2.0",
            "description": "A demo member",
        }
        mcp_shaped = dict(_SCAFFOLD_DATA)
        cli_payload = build_member_data("axm-foo", "axm-demo", cli_shaped)
        mcp_payload = build_member_data("axm-foo", "axm-demo", mcp_shaped)
        assert cli_payload == mcp_payload
        assert cli_payload == {
            "member_name": "axm-foo",
            "workspace_name": "axm-demo",
            "description": "A demo member",
            "org": "acme",
            "license": "Apache-2.0",
            "license_holder": "acme",
            "author_name": "Ada",
            "author_email": "ada@example.com",
        }

    def test_explicit_license_holder_overrides_org(self) -> None:
        """An explicit ``license_holder`` wins over ``org``."""
        payload = build_member_data(
            "axm-foo",
            "axm-demo",
            _SCAFFOLD_DATA,
            license_holder="Umbrella Corp",
        )
        assert payload["license_holder"] == "Umbrella Corp"

    def test_license_holder_defaults_to_org(self) -> None:
        """Without an override the holder falls back to ``org``."""
        payload = build_member_data("axm-foo", "axm-demo", _SCAFFOLD_DATA)
        assert payload["license_holder"] == "acme"


class TestResolveWorkspaceRoot:
    """AC1 — workspace-root resolution lives in the shared seam."""

    def test_workspace_context_returns_target_path(self) -> None:
        """A path that IS a workspace root resolves to itself."""
        from axm_init.checks._workspace import ProjectContext

        target = Path("/tmp/ws")
        with patch(
            "axm_init.checks._workspace.detect_context",
            return_value=ProjectContext.WORKSPACE,
        ):
            assert resolve_workspace_root(target) == target

    def test_member_context_walks_up_to_root(self) -> None:
        """A member path resolves to its parent workspace root."""
        from axm_init.checks._workspace import ProjectContext

        member = Path("/tmp/ws/packages/pkg")
        root = Path("/tmp/ws")
        with (
            patch(
                "axm_init.checks._workspace.detect_context",
                return_value=ProjectContext.MEMBER,
            ),
            patch(
                "axm_init.checks._workspace.find_workspace_root",
                return_value=root,
            ),
        ):
            assert resolve_workspace_root(member) == root
