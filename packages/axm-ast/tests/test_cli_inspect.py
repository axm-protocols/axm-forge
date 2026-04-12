from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.cli import inspect


def _make_result(
    *,
    success: bool = True,
    text: str = "",
    data: dict[str, object] | None = None,
    error: str | None = None,
) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.text = text
    result.data = data or {}
    result.error = error
    return result


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_inspect_variable_shows_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI --symbol logger must print 'variable', not 'class'."""
    text = "variable logger\n  src/pkg/log.py:5\n  type: Logger"
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_result(
        text=text,
        data={"symbol": {"name": "logger", "kind": "variable"}},
    )
    monkeypatch.setattr("axm_ast.tools.inspect.InspectTool", lambda: mock_tool)

    inspect(".", symbol="logger")

    out = capsys.readouterr().out
    assert "variable" in out
    assert "class" not in out


def test_inspect_module_shows_module(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI --symbol models.nodes must print 'module', not 'class'."""
    text = "module models.nodes \u00b7 12 symbols\n  src/pkg/models/nodes.py"
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_result(
        text=text,
        data={"symbol": {"name": "models.nodes", "kind": "module"}},
    )
    monkeypatch.setattr("axm_ast.tools.inspect.InspectTool", lambda: mock_tool)

    inspect(".", symbol="models.nodes")

    out = capsys.readouterr().out
    assert "module" in out


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_cli_inspect_uses_tool_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI inspect output must match InspectTool().execute().text exactly."""
    expected_text = (
        "function do_stuff(x: int, y: int) -> bool\n"
        "  src/pkg/core.py:10-25\n"
        "  Checks stuff."
    )
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_result(
        text=expected_text,
        data={"symbol": {"name": "do_stuff", "kind": "function"}},
    )
    monkeypatch.setattr("axm_ast.tools.inspect.InspectTool", lambda: mock_tool)

    inspect(".", symbol="do_stuff")

    out = capsys.readouterr().out
    assert out.strip() == expected_text.strip()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_inspect_symbol_not_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unknown symbol must write to stderr and exit 1."""
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_result(
        success=False,
        error="Symbol 'nonexistent_xyz' not found",
    )
    monkeypatch.setattr("axm_ast.tools.inspect.InspectTool", lambda: mock_tool)

    with pytest.raises(SystemExit, match="1"):
        inspect(".", symbol="nonexistent_xyz")

    err = capsys.readouterr().err
    assert "nonexistent_xyz" in err


def test_inspect_no_symbol_lists_all(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No --symbol flag lists all symbols (unchanged behavior)."""
    mock_sym = MagicMock()
    mock_sym.name = "MyClass"
    mock_sym.signature = None

    monkeypatch.setattr("axm_ast.cli.get_package", lambda _p: MagicMock())
    monkeypatch.setattr(
        "axm_ast.cli.search_symbols", lambda _pkg, **_kw: [("/f.py", mock_sym)]
    )

    inspect(".")

    out = capsys.readouterr().out
    assert "MyClass" in out
