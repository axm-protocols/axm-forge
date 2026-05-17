"""Split from ``test_nodes.py``."""

from axm_ast.models.nodes import FunctionKind


class TestFunctionKind:
    """Tests for FunctionKind enum."""

    def test_all_values(self) -> None:
        actual = {k.value for k in FunctionKind}
        required = {"function", "method", "property", "classmethod", "staticmethod"}
        assert required.issubset(actual)

    def test_str_enum(self) -> None:
        assert str(FunctionKind.FUNCTION) == "function"
        assert FunctionKind("method") == FunctionKind.METHOD
