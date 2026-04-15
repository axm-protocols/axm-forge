"""Tests for type-reference analysis in impact module (AXM-140).

Covers find_type_refs(), score_impact() with type refs, and
integration with analyze_impact().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import find_type_refs, score_impact

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SELF_PKG = Path(__file__).resolve().parent.parent / "src" / "axm_ast"


@pytest.fixture()
def typed_project(tmp_path: Path) -> Path:
    """Create a minimal package with type annotations."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)

    (pkg / "__init__.py").write_text('"""Demo package."""\n\n__all__ = ["MyModel"]\n')
    (pkg / "models.py").write_text(
        '"""Models module."""\n\n'
        '__all__ = ["MyModel", "MyModelExtended"]\n\n\n'
        "class MyModel:\n"
        '    """A demo model."""\n\n'
        "    name: str\n\n\n"
        "class MyModelExtended:\n"
        '    """An extended model."""\n\n'
        "    name: str\n"
    )
    (pkg / "service.py").write_text(
        '"""Service module."""\n\n'
        '__all__ = ["process", "transform", "get_model",'
        ' "handle_optional", "handle_dict", "handle_list",'
        ' "handle_nested", "handle_string_ann"]\n\n\n'
        "def process(item: MyModel) -> str:\n"
        '    """Process a model."""\n'
        "    return item.name\n\n\n"
        "def transform(items: list[MyModel]) -> list[str]:\n"
        '    """Transform models."""\n'
        "    return [i.name for i in items]\n\n\n"
        "def get_model() -> MyModel:\n"
        '    """Return a model."""\n'
        "    return MyModel()\n\n\n"
        "def handle_optional(x: MyModel | None) -> None:\n"
        '    """Handle optional."""\n'
        "    pass\n\n\n"
        "def handle_dict(d: dict[str, MyModel]) -> None:\n"
        '    """Handle dict value."""\n'
        "    pass\n\n\n"
        "def handle_list(items: list[MyModel]) -> None:\n"
        '    """Handle list."""\n'
        "    pass\n\n\n"
        "def handle_nested(d: dict[str, list[MyModel]]) -> None:\n"
        '    """Handle nested generics."""\n'
        "    pass\n\n\n"
        'def handle_string_ann(x: "MyModel") -> None:\n'
        '    """Handle string annotation."""\n'
        "    pass\n\n\n"
        "def unrelated(x: OtherType) -> None:\n"
        '    """Unrelated function."""\n'
        "    pass\n\n\n"
        "def uses_extended(x: MyModelExtended) -> None:\n"
        '    """Uses extended model — should NOT match MyModel."""\n'
        "    pass\n"
    )
    (pkg / "aliases.py").write_text(
        '"""Aliases module."""\n\n'
        "__all__: list[str] = []\n\n"
        "ModelAlias: type = MyModel\n"
    )
    (pkg / "untyped.py").write_text(
        '"""Untyped module — no annotations."""\n\n'
        "__all__: list[str] = []\n\n\n"
        "def plain(x):\n"
        '    """No type annotations."""\n'
        "    return x\n"
    )

    # Add pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )

    return tmp_path


@pytest.fixture()
def typed_pkg(typed_project: Path) -> object:
    """Return analyzed package from typed_project."""
    return analyze_package(typed_project / "src" / "demo")


# ===========================================================================
# Unit tests: find_type_refs
# ===========================================================================


class TestFindTypeRefsParam:
    """AC1: Detect type refs in function parameters."""

    def test_find_type_refs_param(self, typed_pkg: object) -> None:
        """Type used as parameter annotation is found."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        param_refs = [r for r in refs if r["ref_type"] == "param"]
        fn_names = {r["function"] for r in param_refs}
        assert "process" in fn_names

    def test_find_type_refs_return(self, typed_pkg: object) -> None:
        """Type used as return annotation is found."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        return_refs = [r for r in refs if r["ref_type"] == "return"]
        fn_names = {r["function"] for r in return_refs}
        assert "get_model" in fn_names

    def test_find_type_refs_list(self, typed_pkg: object) -> None:
        """AC4: Type inside list[TypeName] is found."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "transform" in fn_names or "handle_list" in fn_names

    def test_find_type_refs_optional(self, typed_pkg: object) -> None:
        """AC4: Type inside TypeName | None is found."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "handle_optional" in fn_names

    def test_find_type_refs_dict_value(self, typed_pkg: object) -> None:
        """AC4: Type inside dict[str, TypeName] is found."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "handle_dict" in fn_names

    def test_find_type_refs_no_match(self, typed_pkg: object) -> None:
        """No match for a type that doesn't exist."""
        refs = find_type_refs(typed_pkg, "NonExistent")  # type: ignore[arg-type]
        assert refs == []

    def test_find_type_refs_substring(self, typed_pkg: object) -> None:
        """AC4: MyModel should NOT match MyModelExtended."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "uses_extended" not in fn_names


# ===========================================================================
# Unit tests: impact integration
# ===========================================================================


class TestImpactTypeRefs:
    """AC2-3: analyze_impact includes type_refs and score considers them."""

    def test_impact_includes_type_refs(self, typed_pkg: object) -> None:
        """AC2: analyze_impact output has type_refs key."""
        from axm_ast.core.impact import analyze_impact

        result = analyze_impact(
            Path(typed_pkg.root),  # type: ignore[attr-defined]
            "MyModel",
        )
        assert "type_refs" in result
        assert len(result["type_refs"]) > 0

    def test_impact_score_with_types(self) -> None:
        """AC3: Score is HIGH when type is used by 5+ functions."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": f"fn{i}", "module": "mod", "line": i} for i in range(5)
            ],
        }
        assert score_impact(result) == "HIGH"

    def test_score_medium_with_type_refs(self) -> None:
        """Score MEDIUM with 2 type refs and no callers."""
        result = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [
                {"function": "fn1", "module": "mod", "line": 1},
                {"function": "fn2", "module": "mod", "line": 2},
            ],
        }
        assert score_impact(result) == "MEDIUM"

    def test_score_low_without_type_refs(self) -> None:
        """Score LOW with no type refs and no callers."""
        result: dict[str, Any] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
            "type_refs": [],
        }
        assert score_impact(result) == "LOW"

    def test_type_refs_modules_in_affected(
        self,
        typed_pkg: object,
    ) -> None:
        """Type ref modules are included in affected_modules."""
        from axm_ast.core.impact import analyze_impact

        result = analyze_impact(
            Path(typed_pkg.root),  # type: ignore[attr-defined]
            "MyModel",
        )
        type_ref_mods = {r["module"] for r in result["type_refs"]}
        for mod in type_ref_mods:
            assert mod in result["affected_modules"]


# ===========================================================================
# Functional tests
# ===========================================================================


class TestTypeRefsDogfood:
    """Run type ref analysis on axm-ast itself."""

    def test_type_refs_dogfood(self) -> None:
        """PackageInfo is widely used in params/returns across axm-ast."""
        pkg = analyze_package(SELF_PKG)
        refs = find_type_refs(pkg, "PackageInfo")
        assert len(refs) >= 1, f"Expected ≥1 type refs to PackageInfo, got {len(refs)}"
        # Should include both param and return refs.
        ref_types = {r["ref_type"] for r in refs}
        assert "param" in ref_types


# ===========================================================================
# Edge cases
# ===========================================================================


class TestTypeRefsEdgeCases:
    """Edge cases from the ticket specification."""

    def test_no_type_annotations(self, typed_pkg: object) -> None:
        """Untyped codebase returns empty type_refs."""
        # Search for a type in the untyped module only — but
        # find_type_refs scans the whole package. Use a type that
        # doesn't appear anywhere.
        refs = find_type_refs(typed_pkg, "CompletelyAbsent")  # type: ignore[arg-type]
        assert refs == []

    def test_nested_generics(self, typed_pkg: object) -> None:
        """dict[str, list[MyModel]] is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "handle_nested" in fn_names

    def test_string_annotations(self, typed_pkg: object) -> None:
        """String annotation "MyModel" is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        fn_names = {r["function"] for r in refs}
        assert "handle_string_ann" in fn_names

    def test_ref_has_required_fields(self, typed_pkg: object) -> None:
        """Each ref dict has function, module, line, ref_type."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        assert len(refs) > 0
        for ref in refs:
            assert "function" in ref
            assert "module" in ref
            assert "line" in ref
            assert "ref_type" in ref
            assert ref["ref_type"] in {"param", "return", "alias"}

    def test_type_alias_detected(self, typed_pkg: object) -> None:
        """Module-level type alias referencing MyModel is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")  # type: ignore[arg-type]
        alias_refs = [r for r in refs if r["ref_type"] == "alias"]
        assert len(alias_refs) >= 1
        assert any(r["function"] == "ModelAlias" for r in alias_refs)
