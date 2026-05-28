"""Tests for decoupled axm-mcp — pure MCP discovery shell.

After refactor, axm-mcp must have ZERO imports from axm core.
It discovers all tools via entry points only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestNoAxmImports:
    """axm-mcp source must not import from axm core."""

    @staticmethod
    def _get_source_files() -> list[Path]:
        src_dir = Path(__file__).parent.parent.parent / "src" / "axm_mcp"
        return list(src_dir.rglob("*.py"))

    @pytest.mark.parametrize(
        "module_file",
        ["mcp_app.py", "discovery.py", "__init__.py"],
        ids=["mcp_app", "discovery", "init"],
    )
    def test_no_axm_import(self, module_file: str) -> None:
        """The given module must not import from axm core."""
        module_path = (
            Path(__file__).parent.parent.parent / "src" / "axm_mcp" / module_file
        )
        source = module_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("axm."), (
                    f"{module_file} imports from axm core: {node.module}"
                )
                assert node.module != "axm", (
                    f"{module_file} imports from axm core: {node.module}"
                )


class TestNoHardcodedTools:
    """mcp_app.py must NOT hardcode protocol tools or orchestrator helpers."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "init",
            "check",
            "resume",
            "read",
            "configure",
            "get_orchestrator",
        ],
        ids=[
            "init",
            "check",
            "resume",
            "read",
            "configure",
            "get_orchestrator",
        ],
    )
    def test_no_hardcoded_function(self, func_name: str) -> None:
        """mcp_app.py must not define the given function."""
        mcp_app_path = (
            Path(__file__).parent.parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        )
        source = mcp_app_path.read_text()
        assert f"def {func_name}(" not in source, (
            f"{func_name}() is still hardcoded in mcp_app.py"
        )


class TestServerPackageRemoved:
    """server/ package should be removed."""

    def test_no_server_package(self) -> None:
        server_dir = Path(__file__).parent.parent.parent / "src" / "axm_mcp" / "server"
        assert not server_dir.exists(), "server/ package still exists"


class TestPyprojectNoDep:
    """pyproject.toml must NOT list axm-nexus or axm-engine as hard deps."""

    def test_no_private_hard_dependencies(self) -> None:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        import tomllib

        data = tomllib.loads(content)
        deps = data.get("project", {}).get("dependencies", [])

        # axm (public thin wrapper) is allowed — axm-nexus/axm-engine are not
        private_pkgs = {"axm-nexus", "axm-engine"}
        for dep in deps:
            raw = dep.split(">")[0].split("<")[0]
            dep_name = raw.split("=")[0].split("[")[0].strip()
            assert dep_name not in private_pkgs, (
                f"Private package is a hard dependency: {dep}"
            )
