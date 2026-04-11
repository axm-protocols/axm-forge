from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.architecture import (
    _classify_module_role,
    _detect_internal_prefixes,
    _is_internal_import,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_detect_internal_prefixes(tmp_path: Path) -> None:
    """Only directories with __init__.py are detected as internal prefixes."""
    # Two proper packages
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "__init__.py").touch()
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "__init__.py").touch()
    # One plain directory (no __init__.py)
    (tmp_path / "plaindir").mkdir()

    result = _detect_internal_prefixes(tmp_path)

    assert sorted(result) == ["alpha", "beta"]


def test_is_internal_import_match() -> None:
    """An import starting with a known prefix is internal."""
    assert _is_internal_import("pkg.sub", ["pkg"]) is True


def test_is_internal_import_no_match() -> None:
    """An import outside known prefixes is not internal."""
    assert _is_internal_import("external.mod", ["pkg"]) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_imports_returns_leaf(tmp_path: Path) -> None:
    """A module with no imports at all is classified as leaf."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    result = _classify_module_role("pkg.a.b", [], tmp_path)

    assert result == "leaf"


def test_all_external_imports_returns_leaf(tmp_path: Path) -> None:
    """When every import is external/stdlib the module is leaf."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    imports = ["os.path", "sys", "external.mod", "another.lib.util"]
    result = _classify_module_role("pkg.a.b", imports, tmp_path)

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
    result = _classify_module_role("pkg.parent.current", imports, tmp_path)

    assert result == "orchestrator"
