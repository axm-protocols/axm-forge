from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.callees import CalleesTool


@pytest.fixture()
def fake_callees():
    return [
        SimpleNamespace(
            module="pkg.mod",
            symbol="helper",
            line=10,
            call_expression="helper(x, y)",
        ),
        SimpleNamespace(
            module="pkg.util",
            symbol="run",
            line=25,
            call_expression="run()",
        ),
    ]


@pytest.fixture()
def tool():
    return CalleesTool()


def test_callees_output_no_symbol_key(
    tool: CalleesTool, fake_callees: list[SimpleNamespace], tmp_path: Path
) -> None:
    """callee_data dicts must NOT contain a 'symbol' key."""
    with (
        patch("axm_ast.core.flows.find_callees_workspace", return_value=fake_callees),
        patch("axm_ast.core.workspace.analyze_workspace"),
    ):
        result = tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success
    for callee in result.data["callees"]:
        assert "symbol" not in callee


def test_callees_has_call_expression(
    tool: CalleesTool, fake_callees: list[SimpleNamespace], tmp_path: Path
) -> None:
    """Each callee dict must contain a 'call_expression' key."""
    with (
        patch("axm_ast.core.flows.find_callees_workspace", return_value=fake_callees),
        patch("axm_ast.core.workspace.analyze_workspace"),
    ):
        result = tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success
    for callee in result.data["callees"]:
        assert "call_expression" in callee
