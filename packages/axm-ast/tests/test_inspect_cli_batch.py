from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from axm.tools.base import ToolResult


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def mock_tool(monkeypatch: pytest.MonkeyPatch, project_path: Path) -> MagicMock:
    """Mock InspectTool and _resolve_dir so inspect() skips real package loading."""
    mock_cls = MagicMock()
    instance = MagicMock()
    mock_cls.return_value = instance
    monkeypatch.setattr("axm_ast.tools.inspect.InspectTool", mock_cls)
    monkeypatch.setattr("axm_ast.cli._resolve_dir", lambda _p: project_path)
    return instance


@pytest.fixture
def batch_result() -> ToolResult:
    return ToolResult(
        success=True,
        data={
            "symbols": [
                {
                    "name": "search_symbols",
                    "kind": "function",
                    "file": "search.py",
                    "line": 10,
                },
                {
                    "name": "PackageInfo",
                    "kind": "class",
                    "file": "models.py",
                    "line": 20,
                },
            ]
        },
        text=(
            "search_symbols\n  function search.py:10"
            "\n\nPackageInfo\n  class models.py:20"
        ),
    )


def test_inspect_batch_cli(
    mock_tool: MagicMock,
    batch_result: ToolResult,
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--symbols with multiple symbols prints both separated by blank line."""
    from axm_ast.cli import inspect

    mock_tool.execute.return_value = batch_result

    inspect(str(project_path), symbols=["search_symbols", "PackageInfo"])

    mock_tool.execute.assert_called_once_with(
        path=str(project_path), symbols=["search_symbols", "PackageInfo"], source=False
    )
    captured = capsys.readouterr()
    assert "search_symbols" in captured.out
    assert "PackageInfo" in captured.out
    # Blank line separates the two symbols
    assert "\n\n" in captured.out


def test_inspect_batch_json(
    mock_tool: MagicMock,
    batch_result: ToolResult,
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--symbols with --json outputs {"symbols": [...]} with correct length."""
    from axm_ast.cli import inspect

    mock_tool.execute.return_value = batch_result

    inspect(
        str(project_path), symbols=["search_symbols", "PackageInfo"], json_output=True
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "symbols" in data
    assert len(data["symbols"]) == 2


def test_inspect_batch_with_source(
    mock_tool: MagicMock,
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--symbols with --source includes python source blocks."""
    from axm_ast.cli import inspect

    result = ToolResult(
        success=True,
        data={"symbols": [{"name": "search_symbols", "kind": "function"}]},
        text=(
            "search_symbols\n  function\n\n"
            "```python\ndef search_symbols():\n    pass\n```"
        ),
    )
    mock_tool.execute.return_value = result

    inspect(str(project_path), symbols=["search_symbols"], source=True)

    mock_tool.execute.assert_called_once_with(
        path=str(project_path), symbols=["search_symbols"], source=True
    )
    captured = capsys.readouterr()
    assert "```python" in captured.out


def test_inspect_batch_mutual_exclusivity(
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--symbol and --symbols together must error with exit 1."""
    from axm_ast.cli import inspect

    with pytest.raises(SystemExit) as exc_info:
        inspect(str(project_path), symbol="X", symbols=["Y", "Z"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err  # Error message printed to stderr


def test_inspect_batch_single_symbol(
    mock_tool: MagicMock,
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--symbols with a single symbol works via batch path."""
    from axm_ast.cli import inspect

    result = ToolResult(
        success=True,
        data={"symbols": [{"name": "search_symbols", "kind": "function"}]},
        text="search_symbols\n  function",
    )
    mock_tool.execute.return_value = result

    inspect(str(project_path), symbols=["search_symbols"])

    mock_tool.execute.assert_called_once_with(
        path=str(project_path), symbols=["search_symbols"], source=False
    )
    captured = capsys.readouterr()
    assert "search_symbols" in captured.out


def test_inspect_batch_partial_failure(
    mock_tool: MagicMock,
    project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One bad + one good symbol: good rendered, bad shows warning inline."""
    from axm_ast.cli import inspect

    result = ToolResult(
        success=True,
        data={
            "symbols": [
                {
                    "name": "search_symbols",
                    "kind": "function",
                    "file": "search.py",
                    "line": 10,
                },
                {"name": "nonexistent", "error": "Symbol not found"},
            ]
        },
        text=(
            "search_symbols\n  function search.py:10"
            "\n\nnonexistent  \u26a0 Symbol not found"
        ),
    )
    mock_tool.execute.return_value = result

    inspect(str(project_path), symbols=["search_symbols", "nonexistent"])

    captured = capsys.readouterr()
    assert "search_symbols" in captured.out
    assert "\u26a0" in captured.out
    assert "nonexistent" in captured.out
