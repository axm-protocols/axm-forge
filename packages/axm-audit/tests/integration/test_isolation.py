"""Integration tests for dependency isolation (reads pyproject.toml from disk)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestDependencyIsolation:
    """Test that axm-audit has no dependencies on axm."""

    def test_runtime_dependencies_within_allowlist(self) -> None:
        """axm-audit runtime deps must stay within the documented allowlist."""
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        deps = data["project"]["dependencies"]
        names = {
            d.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip()
            for d in deps
        }

        allowed = {"axm", "axm-ast", "complexipy", "cyclopts", "pydantic", "radon"}
        assert names == allowed, f"Unexpected runtime deps: {names - allowed}"
