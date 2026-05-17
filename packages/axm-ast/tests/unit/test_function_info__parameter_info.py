"""Split from ``test_nodes.py``."""

from axm_ast.models.nodes import FunctionInfo, ParameterInfo


def test_signature_with_params() -> None:
    fn = FunctionInfo(
        name="greet",
        params=[ParameterInfo(name="name", annotation="str")],
        return_type="str",
        line_start=1,
        line_end=3,
    )
    assert fn.signature == "def greet(name: str) -> str"
