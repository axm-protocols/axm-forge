"""Split from ``test_nodes.py``."""

import pytest
from pydantic import ValidationError

from axm_ast.models.nodes import ParameterInfo


def test_parameter_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ParameterInfo(name="x", bad="field")  # type: ignore[call-arg]


class TestParameterInfo:
    """Tests for ParameterInfo model."""

    def test_create_minimal(self) -> None:
        p = ParameterInfo(name="x")
        assert p.name == "x"
        assert p.annotation is None
        assert p.default is None

    def test_create_fully_typed(self) -> None:
        p = ParameterInfo(name="path", annotation="Path", default="None")
        assert p.annotation == "Path"
        assert p.default == "None"


class TestParameterInfoFromModels:
    """Tests for ParameterInfo model."""

    def test_annotated_param(self):
        p = ParameterInfo(name="path", annotation="Path")
        assert p.annotation == "Path"

    def test_default_param(self):
        p = ParameterInfo(name="x", default="42")
        assert p.default == "42"

    def test_full_param(self):
        p = ParameterInfo(name="x", annotation="int", default="0")
        assert p.name == "x"
        assert p.annotation == "int"
        assert p.default == "0"
