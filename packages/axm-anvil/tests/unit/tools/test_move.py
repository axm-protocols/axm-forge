from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

import pytest

from axm_anvil.core.move import (
    OverloadPartialMoveError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)
from axm_anvil.core.plan import MovePlan
from axm_anvil.tools.move import MoveTool


def _plan(
    moved: Sequence[str] = ("Foo",),
    imports: Sequence[str] = (),
    constants: Sequence[str] = (),
    warnings: Sequence[str] = (),
) -> MovePlan:
    return MovePlan(
        source_text_new="# new source\n",
        target_text_new="# new target\n",
        moved_names=list(moved),
        imports_added=list(imports),
        constants_added=list(constants),
        warnings=list(warnings),
    )


def test_move_tool_name_and_hint():
    tool = MoveTool()
    assert tool.name == "ast_move"
    assert tool.agent_hint
    assert len(tool.agent_hint) <= 200


def test_format_text_compact():
    plan = _plan(
        moved=("Alpha", "Beta"),
        imports=("os", "sys", "pathlib.Path"),
        warnings=("ruff: unused import removed",),
    )
    tool = MoveTool()
    text = tool._format_text(
        plan,
        from_file="src.py",
        to_file="tgt.py",
    )

    assert "ast_move" in text
    assert "2 symbols" in text
    assert "Moved:" in text
    assert "Dependencies:" in text
    assert len(text.splitlines()) <= 25


def test_mcp_entry_point_discoverable():
    code = (
        "from importlib.metadata import entry_points;"
        "eps = entry_points(group='axm.tools');"
        "match = [(e.name, e.value) for e in eps if e.name == 'ast_move'];"
        "print(match)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ast_move" in result.stdout
    assert "axm_anvil.tools.move:MoveTool" in result.stdout


def test_symbols_csv_parsing(mocker):
    mock = mocker.patch(
        "axm_anvil.tools.move.move_symbols",
        return_value=_plan(moved=("A", "B", "C")),
    )

    tool = MoveTool()
    tool.execute(
        path=".",
        symbols="A,B,C",
        from_file="source.py",
        to_file="target.py",
    )

    args, kwargs = mock.call_args
    passed_symbols = kwargs.get("symbol_names") or args[2]
    assert list(passed_symbols) == ["A", "B", "C"]


def test_execute_returns_tool_result_success(mocker):
    mocker.patch(
        "axm_anvil.tools.move.move_symbols",
        return_value=_plan(moved=("Foo",), imports=("os",)),
    )

    tool = MoveTool()
    result = tool.execute(
        path=".",
        symbols="Foo",
        from_file="source.py",
        to_file="target.py",
    )

    assert result.success is True
    assert result.data is not None
    assert "moved" in result.data
    assert "dependencies_copied" in result.data
    assert "files_modified" in result.data


@pytest.mark.parametrize(
    ("exc", "symbol", "substring"),
    [
        pytest.param(
            SymbolNotFoundError("Foo"), "Foo", "not found", id="symbol_not_found"
        ),
        pytest.param(
            SymbolAlreadyExistsError("Bar"),
            "Bar",
            "already exists",
            id="symbol_already_exists",
        ),
        pytest.param(
            OverloadPartialMoveError("overload group incomplete for foo"),
            "foo",
            "overload",
            id="overload_partial",
        ),
    ],
)
def test_execute_wraps_move_errors(mocker, exc, symbol, substring):
    mocker.patch(
        "axm_anvil.tools.move.move_symbols",
        side_effect=exc,
    )

    tool = MoveTool()
    result = tool.execute(
        path=".",
        symbols=symbol,
        from_file="source.py",
        to_file="target.py",
    )

    assert result.success is False
    assert result.error is not None
    assert substring in result.error.lower()


def test_execute_wraps_generic_exception(mocker):
    mocker.patch(
        "axm_anvil.tools.move.move_symbols",
        side_effect=RuntimeError("boom"),
    )

    tool = MoveTool()
    result = tool.execute(
        path=".",
        symbols="Foo",
        from_file="source.py",
        to_file="target.py",
    )

    assert result.success is False
    assert result.error == "boom"
