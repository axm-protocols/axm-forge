from __future__ import annotations

from axm_ast.hooks.source_body import _dedup_symbols


class TestDedupClassAndMethod:
    def test_dedup_class_and_method(self) -> None:
        assert _dedup_symbols(["Foo", "Foo.validate"]) == ["Foo"]

    def test_dedup_class_and_multiple_methods(self) -> None:
        assert _dedup_symbols(["Foo", "Foo.validate", "Foo._helper"]) == ["Foo"]


class TestDedupMethodOnly:
    def test_dedup_method_only(self) -> None:
        assert _dedup_symbols(["Foo.validate"]) == ["Foo.validate"]


class TestDedupUnrelated:
    def test_dedup_unrelated(self) -> None:
        assert _dedup_symbols(["Foo", "Bar.validate"]) == ["Foo", "Bar.validate"]


class TestDedupBareFunctions:
    def test_dedup_bare_functions(self) -> None:
        assert _dedup_symbols(["func_a", "func_b"]) == ["func_a", "func_b"]


class TestDedupPreservesOrder:
    def test_dedup_preserves_order(self) -> None:
        assert _dedup_symbols(["Foo.validate", "Foo", "Bar"]) == ["Foo", "Bar"]


class TestEdgeCases:
    def test_empty_list(self) -> None:
        assert _dedup_symbols([]) == []

    def test_single_class(self) -> None:
        assert _dedup_symbols(["Foo"]) == ["Foo"]

    def test_single_method(self) -> None:
        assert _dedup_symbols(["Foo.bar"]) == ["Foo.bar"]

    def test_nested_dotted(self) -> None:
        assert _dedup_symbols(["Foo", "Foo.Inner.method"]) == ["Foo"]
