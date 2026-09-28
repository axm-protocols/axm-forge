"""Unit tests for the shared scaffolding seam (``core.scaffolder``)."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from axm_init.core.scaffolder import (
    WorkspaceIdentity,
    build_member_data,
    read_workspace_name,
    resolve_workspace_root,
)

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
            "repository": "acme/axm-demo",
            "docs_url": "https://acme.github.io/axm-demo/axm-foo/",
        }

    def test_resolved_identity_drives_the_links(self) -> None:
        """A resolved identity replaces the name-derived GitHub defaults."""
        identity = WorkspaceIdentity(
            "axm-demo-workspace", "acme/axm-demo", "https://demo.acme.io"
        )
        payload = build_member_data("axm-foo", identity, _SCAFFOLD_DATA)
        assert payload["workspace_name"] == "axm-demo-workspace"
        assert payload["repository"] == "acme/axm-demo"
        assert payload["docs_url"] == "https://demo.acme.io/axm-foo/"

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


class TestBuildMemberDataLegacyKeyword:
    """The former ``workspace_name=`` keyword keeps working, with a warning."""

    def test_workspace_name_keyword_matches_workspace(self) -> None:
        """``workspace_name=`` is deprecated and maps onto ``workspace``."""
        expected = build_member_data(
            "axm-foo", workspace="axm-demo", scaffold_data=_SCAFFOLD_DATA
        )
        with pytest.warns(DeprecationWarning, match="workspace_name"):
            legacy = build_member_data(
                "axm-foo", workspace_name="axm-demo", scaffold_data=_SCAFFOLD_DATA
            )
        assert legacy == expected
        assert legacy["repository"] == "acme/axm-demo"

    def test_workspace_keyword_does_not_warn(self) -> None:
        """The new ``workspace`` parameter, positional or named, stays silent."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            build_member_data("axm-foo", "axm-demo", _SCAFFOLD_DATA)
            build_member_data(
                "axm-foo", workspace="axm-demo", scaffold_data=_SCAFFOLD_DATA
            )

    def test_both_spellings_are_refused(self) -> None:
        """Giving ``workspace`` and ``workspace_name`` together is ambiguous."""
        with pytest.raises(TypeError, match="both"):
            build_member_data(
                "axm-foo",
                "axm-demo",
                _SCAFFOLD_DATA,
                workspace_name="axm-other",
            )

    def test_missing_arguments_are_refused(self) -> None:
        """The optional defaults exist for the legacy keyword only."""
        with pytest.raises(TypeError, match="'workspace'"):
            build_member_data("axm-foo", scaffold_data=_SCAFFOLD_DATA)
        with pytest.raises(TypeError, match="'scaffold_data'"):
            build_member_data("axm-foo", "axm-demo")

    def test_unknown_keyword_is_refused(self) -> None:
        """Only the legacy ``workspace_name`` rides on the extra keywords."""
        unknown: dict[str, Any] = {"workspace_title": "axm-demo"}
        with pytest.raises(TypeError, match="'workspace_title'"):
            build_member_data("axm-foo", "axm-demo", _SCAFFOLD_DATA, **unknown)


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


class TestReadWorkspaceName:
    """AC1 — workspace-name read lives in the shared seam."""

    def test_returns_configured_name_from_pyproject(self, tmp_path: Path) -> None:
        """The ``[project].name`` field is returned when present."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "axm-demo"\n')
        assert read_workspace_name(tmp_path) == "axm-demo"


class TestSeamPurity:
    """AC3 — the seam carries no CLI/MCP coupling."""

    def test_seam_functions_have_no_cli_or_mcp_binding(self) -> None:
        """No argparse/cyclopts/ToolResult symbol is bound in the module."""
        import axm_init.core.scaffolder as scaffolder_module

        bound = set(vars(scaffolder_module))
        forbidden = {"ToolResult", "cyclopts", "argparse", "App", "AXMTool"}
        assert forbidden.isdisjoint(bound)
        assert callable(build_member_data)
        assert callable(read_workspace_name)
        assert callable(resolve_workspace_root)
