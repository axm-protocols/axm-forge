"""Versioned discovery of the explicit commit runtime parameter."""

from __future__ import annotations

import pytest

from axm_git.tools.commit import GitCommitTool


def test_runtime_capability_and_mcp_discovery_are_explicit() -> None:
    """Clients can distinguish the new contract from old ignored kwargs."""
    catalog_module = pytest.importorskip("axm_mcp.facade.catalog")
    catalog = catalog_module.ToolCatalog({"git_commit": GitCommitTool()})
    described = catalog.describe("git_commit")
    assert GitCommitTool.DEPENDENCY_ENVIRONMENT_VERSION == 1
    parameters = {item["name"]: item for item in described["params"]}
    runtime = parameters["dependency_environment"]
    assert not runtime["required"]
    assert "Mapping" in runtime["annotation"]


def test_mcp_facade_consumes_the_runtime_mapping_before_git() -> None:
    """An invalid contract reaches the tool rather than disappearing as kwargs."""
    catalog_module = pytest.importorskip("axm_mcp.facade.catalog")
    catalog = catalog_module.ToolCatalog({"git_commit": GitCommitTool()})
    result = catalog.call(
        "git_commit",
        {
            "path": "/candidate",
            "commits": [{"files": ["candidate.py"], "message": "feat: candidate"}],
            "dependency_environment": {
                "interpreter": "relative/python",
                "package_root": "/candidate",
            },
        },
    )
    assert "dependency interpreter must be absolute" in result
