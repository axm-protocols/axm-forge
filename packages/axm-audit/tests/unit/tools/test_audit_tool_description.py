from __future__ import annotations

from axm_audit.core.auditor import VALID_CATEGORIES
from axm_audit.tools.audit import AuditTool


def test_audit_tool_description_lists_all_valid_categories() -> None:
    description = (AuditTool.__doc__ or "") + "\n" + (AuditTool.execute.__doc__ or "")
    missing = [cat for cat in VALID_CATEGORIES if cat not in description]
    assert not missing, f"AuditTool description missing categories: {missing}"
