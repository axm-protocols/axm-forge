"""Split from ``test_nodes.py``."""

import pytest
from pydantic import ValidationError

from axm_ast.models.nodes import ClassInfo, FunctionInfo


def test_is_public() -> None:
    fn = FunctionInfo(name="greet", line_start=1, line_end=5)
    assert fn.is_public is True


def test_is_private() -> None:
    fn = FunctionInfo(name="_helper", line_start=1, line_end=5)
    assert fn.is_public is False


def test_basic_class():
    cls = ClassInfo(name="Foo", line_start=1, line_end=10)
    assert cls.name == "Foo"
    assert cls.is_public is True
    assert cls.bases == []
    assert cls.methods == []


def test_class_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ClassInfo(name="X", line_start=1, line_end=2, oops=True)  # type: ignore[call-arg]


class TestClassInfo:
    """Tests for ClassInfo model."""

    def test_is_public(self) -> None:
        cls = ClassInfo(name="Parser", line_start=1, line_end=50)
        assert cls.is_public is True

    def test_is_private(self) -> None:
        cls = ClassInfo(name="_Internal", line_start=1, line_end=10)
        assert cls.is_public is False

    def test_with_bases(self) -> None:
        cls = ClassInfo(
            name="MyModel",
            bases=["BaseModel"],
            line_start=1,
            line_end=20,
        )
        assert "BaseModel" in cls.bases
