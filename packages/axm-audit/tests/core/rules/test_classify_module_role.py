from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.architecture.coupling import classify_module_role

# ---------------------------------------------------------------------------
# Behavioral tests — exercise prefix detection / internal-import logic
# indirectly through the public ``classify_module_role`` surface.
# ---------------------------------------------------------------------------


def test_empty_imports_returns_leaf(tmp_path: Path) -> None:
    """A module with no imports at all is classified as leaf."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    result = classify_module_role("pkg.a.b", [], tmp_path)

    assert result == "leaf"


def test_all_external_imports_returns_leaf(tmp_path: Path) -> None:
    """When every import is external/stdlib the module is leaf."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    imports = ["os.path", "sys", "external.mod", "another.lib.util"]
    result = classify_module_role("pkg.a.b", imports, tmp_path)

    assert result == "leaf"


def test_exactly_three_siblings_returns_orchestrator(tmp_path: Path) -> None:
    """Three sibling imports is the boundary — should be orchestrator."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    imports = [
        "pkg.parent.sib1",
        "pkg.parent.sib2",
        "pkg.parent.sib3",
    ]
    result = classify_module_role("pkg.parent.current", imports, tmp_path)

    assert result == "orchestrator"
