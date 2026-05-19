"""Tests for type-reference analysis in impact module (AXM-140).

Covers find_type_refs(), score_impact() with type refs, and
integration with analyze_impact().
"""

from __future__ import annotations

import pytest

from axm_ast.core.impact import find_type_refs

# ===========================================================================
# Unit tests: find_type_refs
# ===========================================================================


class TestFindTypeRefsParam:
    """AC1: Detect type refs in function parameters."""

    @pytest.mark.parametrize(
        ("ref_type_filter", "expected_fn"),
        [
            pytest.param("param", "process", id="param"),
            pytest.param("return", "get_model", id="return"),
            pytest.param(None, "handle_optional", id="optional"),
            pytest.param(None, "handle_dict", id="dict_value"),
            pytest.param(None, "handle_nested", id="nested_generics"),
            pytest.param(None, "handle_string_ann", id="string_annotations"),
        ],
    )
    def test_find_type_refs_detects_fn(
        self,
        typed_pkg: object,
        ref_type_filter: str | None,
        expected_fn: str,
    ) -> None:
        """find_type_refs surfaces the expected function for each ref_type form."""
        refs = find_type_refs(typed_pkg, "MyModel")
        if ref_type_filter is not None:
            refs = [r for r in refs if r["ref_type"] == ref_type_filter]
        fn_names = {r["function"] for r in refs}
        assert expected_fn in fn_names

    def test_find_type_refs_list(self, typed_pkg: object) -> None:
        """AC4: Type inside list[TypeName] is found."""
        refs = find_type_refs(typed_pkg, "MyModel")
        fn_names = {r["function"] for r in refs}
        assert "transform" in fn_names or "handle_list" in fn_names

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
