"""Tests for decoupled axm-mcp — pure MCP discovery shell.

After refactor, axm-mcp must have ZERO imports from axm core.
It discovers all tools via entry points only.
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestNoAxmImports:
    """axm-mcp source must not import from axm core."""

    @staticmethod
    def _get_source_files() -> list[Path]:
        src_dir = Path(__file__).parent.parent / "src" / "axm_mcp"
        return list(src_dir.rglob("*.py"))

    def test_mcp_app_no_axm_import(self) -> None:
        """mcp_app.py must not import from axm."""
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("axm."), (
                    f"mcp_app.py imports from axm core: {node.module}"
                )
                assert node.module != "axm", (
                    f"mcp_app.py imports from axm core: {node.module}"
                )

    def test_discovery_no_axm_import(self) -> None:
        """discovery.py must not import from axm."""
        discovery_path = (
            Path(__file__).parent.parent / "src" / "axm_mcp" / "discovery.py"
        )
        source = discovery_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("axm."), (
                    f"discovery.py imports from axm core: {node.module}"
                )
                assert node.module != "axm", (
                    f"discovery.py imports from axm core: {node.module}"
                )

    def test_init_no_axm_import(self) -> None:
        """__init__.py must not import from axm."""
        init_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "__init__.py"
        source = init_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("axm."), (
                    f"__init__.py imports from axm core: {node.module}"
                )
                assert node.module != "axm", (
                    f"__init__.py imports from axm core: {node.module}"
                )


class TestNoHardcodedTools:
    """mcp_app.py must NOT have hardcoded @mcp.tool init/check/resume/read."""

    def test_no_hardcoded_init(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def init(" not in source, "init() is still hardcoded in mcp_app.py"

    def test_no_hardcoded_check(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def check(" not in source, "check() is still hardcoded in mcp_app.py"

    def test_no_hardcoded_resume(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def resume(" not in source, "resume() is still hardcoded in mcp_app.py"

    def test_no_hardcoded_read(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def read(" not in source, "read() is still hardcoded in mcp_app.py"


class TestNoConfigure:
    """mcp_app.py must NOT have configure() or get_orchestrator()."""

    def test_no_configure(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def configure(" not in source, "configure() is still in mcp_app.py"

    def test_no_get_orchestrator(self) -> None:
        mcp_app_path = Path(__file__).parent.parent / "src" / "axm_mcp" / "mcp_app.py"
        source = mcp_app_path.read_text()
        assert "def get_orchestrator(" not in source, (
            "get_orchestrator() is still in mcp_app.py"
        )


class TestServerPackageRemoved:
    """server/ package should be removed."""

    def test_no_server_package(self) -> None:
        server_dir = Path(__file__).parent.parent / "src" / "axm_mcp" / "server"
        assert not server_dir.exists(), "server/ package still exists"


class TestPyprojectNoDep:
    """pyproject.toml must NOT list axm-core or axm-engine as hard deps."""

    def test_no_private_hard_dependencies(self) -> None:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        import tomllib

        data = tomllib.loads(content)
        deps = data.get("project", {}).get("dependencies", [])

        # axm (public thin wrapper) is allowed — axm-core/axm-engine are not
        private_pkgs = {"axm-core", "axm-engine"}
        for dep in deps:
            raw = dep.split(">")[0].split("<")[0]
            dep_name = raw.split("=")[0].split("[")[0].strip()
            assert dep_name not in private_pkgs, (
                f"Private package is a hard dependency: {dep}"
            )
