"""Split from ``test_nodes.py``."""

from axm_ast.models.nodes import VariableInfo


class TestVariableInfo:
    """Tests for VariableInfo model."""

    def test_create(self) -> None:
        v = VariableInfo(name="__all__", line=5)
        assert v.name == "__all__"
        assert v.annotation is None


class TestVariableInfoFromModels:
    """Tests for VariableInfo model."""

    def test_annotated_variable(self):
        v = VariableInfo(name="x", annotation="int", value_repr="42", line=1)
        assert v.annotation == "int"
        assert v.value_repr == "42"
