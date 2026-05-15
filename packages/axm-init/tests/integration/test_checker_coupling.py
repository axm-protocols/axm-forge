"""Integration tests verifying checker module coupling and fan-out contracts."""

from __future__ import annotations

from pathlib import Path


def test_check_engine_instantiation(tmp_path: Path) -> None:
    """CheckEngine can be instantiated after import refactor."""
    from axm_init.core.checker import CheckEngine

    engine = CheckEngine(tmp_path)
    assert engine.project_path == tmp_path.resolve()


def test_checker_fan_out_at_most_10() -> None:
    """AC1: checker.py fan-out <= 10 (unique module-level imports)."""
    import ast

    checker_path = (
        Path(__file__).resolve().parents[2] / "src" / "axm_init" / "core" / "checker.py"
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
