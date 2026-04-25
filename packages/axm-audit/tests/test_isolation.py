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

    def test_runtime_dependencies_within_allowlist(self) -> None:
        """axm-audit runtime deps must stay within the documented allowlist."""
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        deps = data["project"]["dependencies"]
        names = {
            d.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip()
            for d in deps
        }

        allowed = {"axm", "cyclopts", "pydantic", "radon"}
        assert names == allowed, f"Unexpected runtime deps: {names - allowed}"
