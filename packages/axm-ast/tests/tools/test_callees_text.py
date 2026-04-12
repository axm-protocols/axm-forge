from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from axm_ast.tools.callees import CalleesTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _callee(
    module: str = "axm_ast.cli", line: int = 1, call_expression: str = "foo()"
) -> dict[str, Any]:
    return {"module": module, "line": line, "call_expression": call_expression}


def _ns(
    module: str = "axm_ast.cli", line: int = 1, call_expression: str = "foo()"
) -> SimpleNamespace:
    """Namespace mimicking a callee dataclass returned by find_callees."""
    return SimpleNamespace(module=module, line=line, call_expression=call_expression)


# ---------------------------------------------------------------------------
# Unit tests — _render_text
# ---------------------------------------------------------------------------


def test_text_header_format() -> None:
    callees = [
        _callee("mod.a", 1, "a()"),
        _callee("mod.b", 2, "b()"),
        _callee("mod.c", 3, "c()"),
    ]
    text = CalleesTool._render_text(callees, symbol="Foo.bar")
    assert text.startswith("ast_callees | Foo.bar | 3 callees")


def test_text_callee_lines() -> None:
    callees = [
        _callee("axm_ast.core.flows", 42, "resolve_path(p)"),
        _callee("axm_ast.tools.search", 100, "grep(pattern)"),
    ]
    text = CalleesTool._render_text(callees, symbol="X.y")
    lines = text.splitlines()
    assert lines[1] == "axm_ast.core.flows:42 resolve_path(p)"
    assert lines[2] == "axm_ast.tools.search:100 grep(pattern)"


def test_text_strips_src_prefix() -> None:
    callees = [_callee("src.axm_ast.cli", 10, "run()")]
    text = CalleesTool._render_text(callees, symbol="Main.run")
    body = text.splitlines()[1]
    assert body.startswith("axm_ast.cli:")


def test_text_empty_callees() -> None:
    text = CalleesTool._render_text([], symbol="greet")
    assert text == "ast_callees | greet | 0 callees"


def test_text_workspace_prefix() -> None:
    callees = [_callee("axm-ast::axm_ast.cli", 5, "hello()")]
    text = CalleesTool._render_text(callees, symbol="W.x")
    body = text.splitlines()[1]
    assert body.startswith("axm-ast::axm_ast.cli:")


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_data_unchanged_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_callees = [_ns("axm_ast.cli", 10, "run()"), _ns("axm_ast.core", 20, "init()")]

    # Patch workspace path to raise ValueError so it falls back to package path
    monkeypatch.setattr(
        "axm_ast.core.workspace.analyze_workspace",
        lambda _path: (_ for _ in ()).throw(ValueError("not a workspace")),
    )
    monkeypatch.setattr(
        "axm_ast.core.cache.get_package",
        lambda _path: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "axm_ast.core.flows.find_callees",
        lambda _pkg, _sym: fake_callees,
    )

    tool = CalleesTool()
    result = tool.execute(path="/tmp", symbol="Foo.bar")

    assert result.success is True
    assert isinstance(result.data["callees"], list)
    assert isinstance(result.data["count"], int)
    assert result.text is not None


def test_callees_text_on_real_package() -> None:
    tool = CalleesTool()
    result = tool.execute(
        path="/Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/axm-ast",
        symbol="CalleesTool.execute",
    )
    assert result.success is True
    assert result.text is not None
    assert result.text.startswith("ast_callees |")
    body_lines = result.text.splitlines()[1:]
    assert len(body_lines) == result.data["count"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_error_result_no_symbol() -> None:
    tool = CalleesTool()
    result = tool.execute(symbol=None)
    assert result.success is False
    assert result.text is None


def test_module_without_src_prefix() -> None:
    callees = [_callee("tests.test_callees", 5, "check()")]
    text = CalleesTool._render_text(callees, symbol="T.run")
    body = text.splitlines()[1]
    assert body.startswith("tests.test_callees:")


def test_very_long_module_name() -> None:
    long_mod = "axm_ast.tools.very.deeply.nested.module.path"
    callees = [_callee(long_mod, 999, "deep_call()")]
    text = CalleesTool._render_text(callees, symbol="Z")
    body = text.splitlines()[1]
    assert body.startswith(f"{long_mod}:999")
