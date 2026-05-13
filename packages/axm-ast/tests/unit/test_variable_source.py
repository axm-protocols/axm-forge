from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.models import VariableInfo
from axm_ast.tools.inspect_detail import build_detail


def _make_variable(
    name: str = "MY_VAR",
    line: int = 5,
    annotation: str | None = "int",
    value_repr: str | None = "42",
) -> SimpleNamespace:
    """Create a minimal VariableInfo-like object."""
    ns = SimpleNamespace(
        name=name, line=line, annotation=annotation, value_repr=value_repr
    )
    ns.__class__.__name__ = "VariableInfo"  # isinstance check uses real class
    return ns


@pytest.fixture()
def var_info():
    from axm_ast.models import VariableInfo

    return VariableInfo(name="MY_VAR", line=5, annotation="int", value_repr="42")


class TestVariableSourceIncluded:
    """AC1: build_detail(variable, source=True, abs_path=...) includes source key."""

    def test_variable_source_included(self, var_info: VariableInfo) -> None:
        with patch(
            "axm_ast.tools.inspect_detail.read_source", return_value="MY_VAR: int = 42"
        ) as mock_rs:
            detail = build_detail(
                var_info, file="f.py", abs_path="/tmp/f.py", source=True
            )

        assert "source" in detail
        assert detail["source"] == "MY_VAR: int = 42"
        mock_rs.assert_called_once_with("/tmp/f.py", 5, 5)


class TestVariableSourceNotIncluded:
    """AC2: build_detail(variable, source=False) does NOT include source key."""

    def test_variable_source_not_included_by_default(
        self, var_info: VariableInfo
    ) -> None:
        detail = build_detail(var_info, file="f.py")

        assert "source" not in detail


class TestVariableSourceEdgeCases:
    """Edge cases for variable source handling."""

    def test_variable_source_true_no_abs_path(self, var_info: VariableInfo) -> None:
        """source=True but abs_path is empty -> no source key."""
        detail = build_detail(var_info, file="f.py", abs_path="", source=True)

        assert "source" not in detail
