"""Integration tests verifying copier adapter coupling and fan-out contracts."""

from __future__ import annotations

from pathlib import Path


def test_copier_config_instantiation(tmp_path: Path) -> None:
    """CopierConfig can be instantiated after import refactor."""
    from axm_init.adapters.copier import CopierConfig

    config = CopierConfig(
        template_path=tmp_path / "template",
        destination=tmp_path / "dest",
        data={"project_name": "test"},
    )
    assert config.template_path == tmp_path / "template"


def test_copier_fan_out_at_most_10() -> None:
    """AC2: copier.py fan-out <= 10 (unique module-level imports)."""
    import ast

    copier_path = (
        Path(__file__).resolve().parents[2]
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

    assert len(modules) <= 10, (
        f"copier.py fan-out is {len(modules)} (max 10): {sorted(modules)}"
    )
