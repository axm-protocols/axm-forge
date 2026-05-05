"""Integration tests for rich output (filesystem reads of source modules)."""

from __future__ import annotations

import pytest


class TestComplexityAfterRefactoring:
    """Verify refactored functions have cc < 10."""

    @pytest.mark.parametrize(
        "module_path,function_name",
        [
            ("src/axm_audit/formatters.py", "format_report"),
            ("src/axm_audit/formatters.py", "_format_check_details"),
            ("src/axm_audit/core/rules/security.py", "check"),
            ("src/axm_audit/core/rules/dependencies.py", "check"),
            ("src/axm_audit/core/rules/structure.py", "check"),
            ("src/axm_audit/core/rules/architecture/__init__.py", "check"),
        ],
    )
    def test_function_cc_under_10(self, module_path: str, function_name: str) -> None:
        """Each refactored function must have cc < 10."""
        from pathlib import Path

        from radon.complexity import cc_visit

        project_root = Path(__file__).parent.parent.parent
        source = (project_root / module_path).read_text()
        blocks = cc_visit(source)

        for block in blocks:
            if block.name == function_name:
                assert block.complexity < 10, (
                    f"{module_path}:{function_name} has cc={block.complexity}, "
                    f"expected < 10"
                )
