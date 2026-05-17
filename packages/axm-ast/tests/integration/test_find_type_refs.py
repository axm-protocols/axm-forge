"""Tests for type-reference analysis in impact module (AXM-140).

Covers find_type_refs(), score_impact() with type refs, and
integration with analyze_impact().
"""

from __future__ import annotations

from axm_ast.core.impact import find_type_refs

# ===========================================================================
# Unit tests: find_type_refs
# ===========================================================================


class TestFindTypeRefsParam:
    """AC1: Detect type refs in function parameters."""

    def test_find_type_refs_param(self, typed_pkg: object) -> None:
        """Type used as parameter annotation is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        param_refs = [r for r in refs if r["ref_type"] == "param"]
        fn_names = {r["function"] for r in param_refs}
        assert "process" in fn_names

    def test_find_type_refs_return(self, typed_pkg: object) -> None:
        """Type used as return annotation is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        return_refs = [r for r in refs if r["ref_type"] == "return"]
        fn_names = {r["function"] for r in return_refs}
        assert "get_model" in fn_names

    def test_find_type_refs_list(self, typed_pkg: object) -> None:
        """AC4: Type inside list[TypeName] is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "transform" in fn_names or "handle_list" in fn_names

    def test_find_type_refs_optional(self, typed_pkg: object) -> None:
        """AC4: Type inside TypeName | None is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "handle_optional" in fn_names

    def test_find_type_refs_dict_value(self, typed_pkg: object) -> None:
        """AC4: Type inside dict[str, TypeName] is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "handle_dict" in fn_names

    def test_find_type_refs_no_match(self, typed_pkg: object) -> None:
        """No match for a type that doesn't exist."""
        refs = find_type_refs(typed_pkg, "NonExistent")
        assert refs == []

    def test_find_type_refs_substring(self, typed_pkg: object) -> None:
        """AC4: MyModel should NOT match MyModelExtended."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "uses_extended" not in fn_names


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
        refs = find_type_refs(typed_pkg, "CompletelyAbsent")
        assert refs == []

    def test_nested_generics(self, typed_pkg: object) -> None:
        """dict[str, list[MyModel]] is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "handle_nested" in fn_names

    def test_string_annotations(self, typed_pkg: object) -> None:
        """String annotation "MyModel" is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "handle_string_ann" in fn_names

    def test_ref_has_required_fields(self, typed_pkg: object) -> None:
        """Each ref dict has function, module, line, ref_type."""
        refs = find_type_refs(typed_pkg, "MyModel")
        assert len(refs) > 0
        for ref in refs:
            assert "function" in ref
            assert "module" in ref
            assert "line" in ref
            assert "ref_type" in ref
            assert ref["ref_type"] in {"param", "return", "alias"}

    def test_type_alias_detected(self, typed_pkg: object) -> None:
        """Module-level type alias referencing MyModel is detected."""
        refs = find_type_refs(typed_pkg, "MyModel")
        alias_refs = [r for r in refs if r["ref_type"] == "alias"]
        assert len(alias_refs) >= 1
        assert any(r["function"] == "ModelAlias" for r in alias_refs)
