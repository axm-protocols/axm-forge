from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


class TestCopierLazyImports:
    """Verify copier module works at runtime after TYPE_CHECKING refactor."""

    def test_copier_imports_at_runtime(self) -> None:
        """Importing copier adapter in a fresh interpreter raises no ImportError."""
        code = textwrap.dedent("""
            from axm_init.adapters.copier import CopierAdapter, CopierConfig
            print("OK")
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"ImportError: {result.stderr}"
        assert "OK" in result.stdout

    def test_copier_config_instantiation(self, tmp_path: Path) -> None:
        """CopierConfig can be instantiated after import refactor."""
        from axm_init.adapters.copier import CopierConfig

        config = CopierConfig(
            template_path=tmp_path / "template",
            destination=tmp_path / "dest",
            data={"project_name": "test"},
        )
        assert config.template_path == tmp_path / "template"

    def test_copier_adapter_instantiation(self) -> None:
        """CopierAdapter can be instantiated after import refactor."""
        from axm_init.adapters.copier import CopierAdapter

        adapter = CopierAdapter()
        assert hasattr(adapter, "copy")
        assert hasattr(adapter, "_do_copy")

    def test_copier_fan_out_at_most_10(self) -> None:
        """AC2: copier.py fan-out <= 10 (unique module-level imports)."""
        import ast

        copier_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "axm_init"
            / "adapters"
            / "copier.py"
        )
        tree = ast.parse(copier_path.read_text())

        modules: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            # Skip TYPE_CHECKING blocks
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "TYPE_CHECKING"
            ):
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])

        assert (
            len(modules) <= 10
        ), f"copier.py fan-out is {len(modules)} (max 10): {sorted(modules)}"
