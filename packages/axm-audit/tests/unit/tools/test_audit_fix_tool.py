"""Unit tests for axm_audit.tools.audit_fix entry-point resolution."""

from __future__ import annotations

import importlib.metadata

from axm_audit.tools.audit_fix import AuditFixTool


def test_axm_tools_entry_point_resolves_audit_fix() -> None:
    """AC7: 'audit_fix' is registered in the axm.tools entry-point group."""
    eps = importlib.metadata.entry_points(group="axm.tools")
    names = {ep.name for ep in eps}

    assert "audit_fix" in names, (
        "audit_fix entry point not registered; re-run `uv sync` or "
        "`uv pip install -e .` after editing pyproject.toml"
    )

    audit_fix_ep = next(ep for ep in eps if ep.name == "audit_fix")
    loaded = audit_fix_ep.load()
    assert loaded is AuditFixTool
