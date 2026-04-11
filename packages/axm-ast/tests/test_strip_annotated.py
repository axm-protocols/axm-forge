from __future__ import annotations

from axm_ast.models.nodes import FunctionInfo, ParameterInfo, _strip_annotated

# ── Unit tests ──────────────────────────────────────────────────────


class TestStripAnnotated:
    """Unit tests for _strip_annotated helper."""

    def test_strip_simple_annotated(self) -> None:
        assert _strip_annotated("Annotated[str, Parameter(...)]") == "str"

    def test_strip_nested_type(self) -> None:
        assert _strip_annotated("Annotated[dict[str, int], Meta()]") == "dict[str, int]"

    def test_strip_multiline_annotated(self) -> None:
        raw = "Annotated[\n    str,\n    Parameter(help='...'),\n]"
        assert _strip_annotated(raw) == "str"

    def test_no_strip_plain_type(self) -> None:
        assert _strip_annotated("str") == "str"

    def test_no_strip_generic(self) -> None:
        assert _strip_annotated("list[str]") == "list[str]"


# ── Functional tests ────────────────────────────────────────────────


class TestFunctionInfoSignatureStrips:
    """Functional tests: FunctionInfo.model_post_init strips Annotated."""

    def test_function_info_signature_strips_annotated(self) -> None:
        info = FunctionInfo(
            name="greet",
            line_start=1,
            line_end=3,
            docstring=None,
            params=[
                ParameterInfo(
                    name="name", annotation="Annotated[str, Parameter(help='user')]"
                ),
            ],
            return_type="None",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "name: str" in info.signature

    def test_search_cyclopts_function(self) -> None:
        """Simulate a cyclopts-annotated CLI function parsed result."""
        info = FunctionInfo(
            name="serve",
            line_start=10,
            line_end=30,
            docstring="Start server.",
            params=[
                ParameterInfo(
                    name="host", annotation="Annotated[str, Parameter(help='Host')]"
                ),
                ParameterInfo(
                    name="port", annotation="Annotated[int, Parameter(help='Port')]"
                ),
                ParameterInfo(name="verbose", annotation="bool", default="False"),
            ],
            return_type="None",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "host: str" in info.signature
        assert "port: int" in info.signature
        assert "verbose: bool" in info.signature


# ── Edge cases ──────────────────────────────────────────────────────


class TestStripAnnotatedEdgeCases:
    """Edge-case coverage for _strip_annotated."""

    def test_multiple_annotated_params(self) -> None:
        """Function with 3+ Annotated parameters — all stripped independently."""
        info = FunctionInfo(
            name="f",
            line_start=1,
            line_end=5,
            docstring=None,
            params=[
                ParameterInfo(name="a", annotation="Annotated[str, X]"),
                ParameterInfo(name="b", annotation="Annotated[int, Y]"),
                ParameterInfo(name="c", annotation="Annotated[float, Z]"),
            ],
            return_type=None,
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "a: str" in info.signature
        assert "b: int" in info.signature
        assert "c: float" in info.signature

    def test_annotated_with_multiple_metadata(self) -> None:
        assert _strip_annotated("Annotated[str, A, B, C]") == "str"

    def test_annotated_as_return_type(self) -> None:
        """Return type Annotated[bool, ...] should also be stripped."""
        info = FunctionInfo(
            name="check",
            line_start=1,
            line_end=3,
            docstring=None,
            params=[],
            return_type="Annotated[bool, Meta()]",
            is_async=False,
        )
        assert info.signature is not None
        assert "Annotated" not in info.signature
        assert "-> bool" in info.signature

    def test_empty_annotated(self) -> None:
        """Annotated[str] with single arg (unusual but valid)."""
        assert _strip_annotated("Annotated[str]") == "str"
