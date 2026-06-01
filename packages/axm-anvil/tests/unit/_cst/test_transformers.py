from __future__ import annotations

import libcst as cst
import pytest

from axm_anvil._cst.transformers import (
    AttributeRewriter,
    ProtectConditionalImports,
    RemoveSymbols,
    RenameSymbols,
    SyncDunderAll,
)


def test_remove_symbols_removes_class() -> None:
    source = "class A:\n    pass\n\nclass B:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"A"}))
    code = new.code
    assert "class A" not in code
    assert "class B" in code


def test_remove_symbols_preserves_formatting() -> None:
    source = "class A:\n    pass\n\n# section comment\n\nclass B:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"A"}))
    assert "class B:\n    pass" in new.code
    assert "# section comment" in new.code


def test_remove_symbols_skips_non_target() -> None:
    source = "class A:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"X"}))
    assert new.code == source


def _rewrite(
    source: str,
    *,
    old_module_alias: str,
    new_module: str,
    symbols: set[str],
) -> tuple[str, AttributeRewriter]:
    tree = cst.parse_module(source)
    wrapper = cst.metadata.MetadataWrapper(tree)
    transformer = AttributeRewriter(
        old_module_alias=old_module_alias,
        new_module=new_module,
        symbols=symbols,
    )
    new_tree = wrapper.visit(transformer)
    return new_tree.code, transformer


def test_attribute_rewriter_simple_chain() -> None:
    source = "import pkg.old\npkg.old.Foo()\n"
    result, _ = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo()" in result
    assert "pkg.old.Foo" not in result


def test_attribute_rewriter_with_alias() -> None:
    source = "import pkg.old as om\nom.Foo()\n"
    result, _ = _rewrite(
        source,
        old_module_alias="om",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo()" in result


def test_attribute_rewriter_method_chain_preserved() -> None:
    source = "pkg.old.Foo.bar().baz\n"
    result, _ = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo.bar().baz" in result


def test_attribute_rewriter_subscript_chain() -> None:
    source = "pkg.old.Foo[key]\n"
    result, _ = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo[key]" in result


def test_attribute_rewriter_leaves_other_symbols() -> None:
    source = "pkg.old.Foo\npkg.old.Other\n"
    result, _ = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo" in result
    assert "pkg.old.Other" in result


def test_attribute_rewriter_reports_remaining_usages() -> None:
    source = "import pkg.old\npkg.old.Foo\npkg.old.Other\n"
    _, transformer = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert transformer.kept_usages == 1


def test_attribute_rewriter_ignores_shadowed_name() -> None:
    source = "import pkg.old\ndef f(pkg):\n    return pkg.old.Foo\n"
    result, _ = _rewrite(
        source,
        old_module_alias="pkg.old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "return pkg.old.Foo" in result


def test_attribute_rewriter_leftmost_not_a_name_is_left() -> None:
    # A call result attribute (``f().old.Foo``) has no leftmost ``Name``,
    # so ``_leftmost_is_safe`` returns False and the chain is untouched.
    source = "f().old.Foo\n"
    result, transformer = _rewrite(
        source,
        old_module_alias="f().old",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "f().old.Foo" in result
    assert transformer.kept_usages == 0


def test_attribute_rewriter_unbound_alias_still_rewrites() -> None:
    # ``mod`` is never imported/defined: ScopeProvider has no binding, so
    # ``_leftmost_is_safe`` treats it as safe (empty assignments) and rewrites.
    source = "mod.Foo()\n"
    result, _ = _rewrite(
        source,
        old_module_alias="mod",
        new_module="pkg.new",
        symbols={"Foo"},
    )
    assert "pkg.new.Foo()" in result


# --- ProtectConditionalImports -------------------------------------------


def _protect(source: str) -> str:
    tree = cst.parse_module(source)
    return tree.visit(ProtectConditionalImports()).code


def test_protect_try_except_imports_tagged() -> None:
    source = (
        "try:\n    import fast as impl\nexcept ImportError:\n    import slow as impl\n"
    )
    result = _protect(source)
    assert result.count("# noqa: F401") == 2
    assert "import fast as impl  # noqa: F401" in result
    assert "import slow as impl  # noqa: F401" in result


def test_protect_try_else_branch_tagged() -> None:
    source = "try:\n    import a\nexcept ImportError:\n    pass\nelse:\n    import b\n"
    result = _protect(source)
    assert "import a  # noqa: F401" in result
    assert "import b  # noqa: F401" in result


def test_protect_if_guard_body_tagged() -> None:
    source = "import os\nif sys.version_info >= (3, 12):\n    import tomllib as toml\n"
    result = _protect(source)
    # Only the guarded import inside the ``if`` body is tagged; the bare
    # module-level ``import os`` outside any guard is left alone.
    assert "import tomllib as toml  # noqa: F401" in result
    assert "import os\n" in result
    assert result.count("# noqa: F401") == 1


def test_protect_skips_nested_try() -> None:
    # A try guard nested inside a function (depth != 0) is left untouched.
    source = (
        "def f():\n"
        "    try:\n        import a\n    except ImportError:\n        import b\n"
    )
    result = _protect(source)
    assert "# noqa: F401" not in result


def test_protect_skips_nested_if() -> None:
    source = "def f():\n    if FLAG:\n        import a\n"
    result = _protect(source)
    assert "# noqa: F401" not in result


def test_protect_idempotent_existing_noqa() -> None:
    source = "try:\n    import a  # noqa: F401\nexcept ImportError:\n    import b\n"
    result = _protect(source)
    # The already-tagged import is not double-tagged.
    assert result.count("import a  # noqa: F401") == 1
    assert "import b  # noqa: F401" in result


def test_protect_leaves_non_import_lines() -> None:
    source = "if FLAG:\n    x = 1\n"
    result = _protect(source)
    assert "# noqa" not in result
    assert "x = 1" in result


# --- RenameSymbols -------------------------------------------------------


def _rename(source: str, mapping: dict[str, str]) -> str:
    tree = cst.parse_module(source)
    return tree.visit(RenameSymbols(mapping)).code


def test_rename_class_definition_and_references() -> None:
    source = "class Old:\n    pass\n\nx = Old()\n"
    result = _rename(source, {"Old": "New"})
    assert "class New:" in result
    assert "x = New()" in result
    assert "Old" not in result


def test_rename_preserves_attribute_member_name() -> None:
    # ``obj.Old`` must keep its member; only a bare ``Old`` head is renamed.
    source = "obj.Old\nOld\n"
    result = _rename(source, {"Old": "New"})
    assert "obj.Old" in result
    assert "\nNew\n" in result


def test_rename_rewrites_string_forward_reference() -> None:
    source = "def f(x: 'Old') -> None:\n    pass\n"
    result = _rename(source, {"Old": "New"})
    assert "'New'" in result
    assert "Old" not in result


def test_rename_leaves_non_string_annotation() -> None:
    source = "def f(x: int) -> None:\n    pass\n"
    result = _rename(source, {"Old": "New"})
    assert result == source


def test_rename_leaves_string_annotation_without_match() -> None:
    source = "def f(x: 'int') -> None:\n    pass\n"
    result = _rename(source, {"Old": "New"})
    assert "'int'" in result


def test_rename_leaves_unparsable_string_annotation() -> None:
    source = "def f(x: 'not valid python !!') -> None:\n    pass\n"
    result = _rename(source, {"Old": "New"})
    assert "'not valid python !!'" in result


# --- SyncDunderAll ------------------------------------------------------


def _sync(source: str, remove: set[str], add: list[str]) -> str:
    tree = cst.parse_module(source)
    return tree.visit(SyncDunderAll(remove, add)).code


def test_sync_removes_and_adds_names() -> None:
    source = '__all__ = ["a", "b"]\n'
    result = _sync(source, {"a"}, ["c"])
    assert '"a"' not in result
    assert '"b"' in result
    assert '"c"' in result


def test_sync_is_idempotent_for_existing_add() -> None:
    source = '__all__ = ["a", "b"]\n'
    result = _sync(source, set(), ["b"])
    assert result.count('"b"') == 1


def test_sync_handles_tuple_literal() -> None:
    source = '__all__ = ("a", "b")\n'
    result = _sync(source, {"b"}, ["c"])
    assert '"b"' not in result
    assert '"c"' in result


def test_sync_ignores_non_dunder_all_assign() -> None:
    source = 'other = ["a"]\n'
    result = _sync(source, {"a"}, ["c"])
    assert result == source


def test_sync_ignores_non_list_tuple_value() -> None:
    source = "__all__ = some_func()\n"
    result = _sync(source, {"a"}, ["c"])
    assert result == source


def test_sync_leaves_non_string_elements_present() -> None:
    # A non-string element (a name reference) is kept untouched; adds still apply.
    source = "__all__ = [SOME_NAME]\n"
    result = _sync(source, {"a"}, ["c"])
    assert "SOME_NAME" in result
    assert '"c"' in result


def test_sync_concatenated_string_element_removed() -> None:
    source = '__all__ = ["ab" "cd", "keep"]\n'
    result = _sync(source, {"abcd"}, [])
    assert "abcd" not in result.replace('"keep"', "")
    assert '"keep"' in result


def test_sync_skips_nested_dunder_all() -> None:
    # A function-local ``__all__`` (depth != 0) is left untouched.
    source = 'def f():\n    __all__ = ["a"]\n'
    result = _sync(source, {"a"}, [])
    assert '"a"' in result


# --- RemoveSymbols (assignments) ----------------------------------------


@pytest.mark.parametrize(
    ("source", "target", "removed_fragment", "kept_fragment"),
    [
        ("X = 1\nY = 2\n", "X", "X = 1", "Y = 2"),
        ("X: int = 1\nY: int = 2\n", "X", "X: int", "Y: int"),
        ("def a():\n    pass\n\ndef b():\n    pass\n", "a", "def a(", "def b("),
    ],
    ids=["plain_assign", "annotated_assign", "function"],
)
def test_remove_symbols_drops_targeted_top_level_node(
    source: str, target: str, removed_fragment: str, kept_fragment: str
) -> None:
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({target}))
    assert removed_fragment not in new.code
    assert kept_fragment in new.code


def test_remove_symbols_keeps_nested_definition() -> None:
    # A class method matching the target name is NOT removed (depth != 0).
    source = "class C:\n    def a(self):\n        pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"a"}))
    assert "def a(self)" in new.code


def test_remove_symbols_keeps_multi_target_assignment() -> None:
    # ``X = Y = 1`` has a single target list of length 1 in libcst only for
    # one assignment target group; a tuple target is not a bare Name match.
    source = "X, Z = 1, 2\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"X"}))
    assert "X, Z = 1, 2" in new.code
