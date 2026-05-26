from __future__ import annotations

import libcst as cst

from axm_anvil._cst.transformers import _AttributeRewriter


def _rewrite(
    source: str,
    *,
    old_module_alias: str,
    new_module: str,
    symbols: set[str],
) -> tuple[str, _AttributeRewriter]:
    tree = cst.parse_module(source)
    wrapper = cst.metadata.MetadataWrapper(tree)
    transformer = _AttributeRewriter(
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
