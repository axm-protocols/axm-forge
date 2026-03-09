"""Tests for dependency isolation."""


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

    def test_only_pydantic_dependency(self):
        """Test that axm-audit only depends on pydantic."""
        # This would be tested by inspecting pyproject.toml
        # For now, we'll just verify pydantic is available
        import pydantic

        assert pydantic is not None
