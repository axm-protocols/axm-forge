from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


class TestCheckerLazyImports:
    """Verify checker module works at runtime after TYPE_CHECKING refactor."""

    def test_checker_imports_at_runtime(self) -> None:
        """Importing checker in a fresh interpreter raises no ImportError."""
        code = textwrap.dedent("""
            from axm_init.core.checker import CheckEngine
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

    def test_check_engine_instantiation(self, tmp_path: Path) -> None:
        """CheckEngine can be instantiated after import refactor."""
        from axm_init.core.checker import CheckEngine

        engine = CheckEngine(tmp_path)
        assert engine.project_path == tmp_path.resolve()

    def test_discover_checks_returns_registry(self) -> None:
        """_discover_checks still finds check modules at runtime."""
        from axm_init.core.checker import _discover_checks

        registry = _discover_checks()
        assert isinstance(registry, dict)
        assert len(registry) > 0
        for category, fns in registry.items():
            assert isinstance(category, str)
            assert all(callable(fn) for fn in fns)

    def test_checker_fan_out_at_most_10(self) -> None:
        """AC1: checker.py fan-out <= 10 (unique module-level imports)."""
        import ast

        checker_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "axm_init"
            / "core"
            / "checker.py"
        )
        tree = ast.parse(checker_path.read_text())

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

        assert len(modules) <= 10, (
            f"checker.py fan-out is {len(modules)} (max 10): {sorted(modules)}"
        )
