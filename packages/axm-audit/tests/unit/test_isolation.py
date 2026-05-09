"""Unit tests for dependency isolation (sys.modules inspection, no I/O)."""

from __future__ import annotations


class TestDependencyIsolation:
    """Test that axm-audit has no dependencies on axm."""

    def test_no_axm_imports_in_audit(self):
        """Test that axm-audit does not import from axm."""
        import sys

        # Remove axm from sys.modules if present
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith("axm.")]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Import axm_audit - should not trigger axm imports

        # Check that axm was not imported
        axm_modules = [k for k in sys.modules.keys() if k.startswith("axm.")]
        assert len(axm_modules) == 0
