"""Installed dist-info providers are shared by CLI/node/MCP resolvers."""

from __future__ import annotations

import json
import sys

import pytest

from axm.tools import load_tool
from axm.tools.discovery import tool_entry_points
from axm.tools.manifest_discovery import declarative_tool_references

pytestmark = pytest.mark.integration


@pytest.fixture
def installed(tmp_path, monkeypatch):
    name = "fixture_ui_addon"
    monkeypatch.delitem(sys.modules, name, raising=False)
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "ui").mkdir()
    raw = {
        "schema_version": 1,
        "addon_id": "fixture",
        "bundle_sha256": "a" * 64,
        "tools": [
            {
                "name": "fixture_ui_read",
                "handler": "fixture_ui_read",
                "description": "Read presentation state",
                "inputSchema": {"type": "object", "additionalProperties": False},
                "outputSchema": {"type": "object"},
            }
        ],
    }
    manifest = package / "ui" / "tools.json"
    manifest.write_text(json.dumps(raw))
    metadata = tmp_path / "fixture_addon-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fixture-addon\nVersion: 1.0\n"
    )
    (metadata / "entry_points.txt").write_text(
        "[axm.tool_manifests]\nfixture = fixture_ui_addon\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return manifest, metadata, raw


def test_real_installed_metadata_is_in_common_resolver(installed):
    references = tool_entry_points()
    assert "fixture_ui_read" in references
    adapter = load_tool("fixture_ui_read")
    assert adapter.name == "fixture_ui_read"
    result = adapter.execute()
    assert not result.success
    assert result.data == {"status": "unavailable"}


def test_missing_resource_is_explicit_without_breaking_legacy(installed, caplog):
    path, _, _ = installed
    path.unlink()
    assert "fixture_ui_read" not in tool_entry_points()
    assert "declarative provider fixture unavailable" in caplog.text


def test_malformed_manifest_and_owner_mismatch_fail_closed(installed):
    path, _, raw = installed
    raw["addon_id"] = "other"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="does not own"):
        declarative_tool_references()


def test_python_ui_name_collision_is_rejected(installed):
    _, metadata, _ = installed
    (metadata / "entry_points.txt").write_text(
        "[axm.tool_manifests]\nfixture = fixture_ui_addon\n"
        "[axm.tools]\nfixture_ui_read = axm:ToolResult\n"
    )
    with pytest.raises(ValueError, match="collides"):
        tool_entry_points()
