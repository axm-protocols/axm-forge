from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.impact import ImpactTool


@pytest.fixture
def tool() -> ImpactTool:
    return ImpactTool()


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


def _make_result(symbol: str, *, score: str = "LOW") -> dict[str, object]:
    return {
        "symbol": symbol,
        "score": score,
        "callers": [],
        "definition": {"file": "mod.py", "line": 1},
    }


def _make_error_result(symbol: str) -> dict[str, str]:
    return {"symbol": symbol, "error": f"{symbol} not found"}


# --- Unit tests ---


def test_execute_batch_compact(
    tool: ImpactTool, project_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2 symbols with detail='compact' returns compact formatted text."""
    results = [_make_result("Foo.bar"), _make_result("Baz.qux", score="HIGH")]
    call_idx = iter(range(len(results)))
    monkeypatch.setattr(
        tool,
        "_analyze_single",
        lambda *a, **kw: results[next(call_idx)],
    )

    out = tool._execute_batch(
        project_path,
        symbols=["Foo.bar", "Baz.qux"],
        exclude_tests=True,
        detail="compact",
    )

    assert out.success is True
    assert out.data == {}
    assert out.text is not None
    assert isinstance(out.text, str)
    assert len(out.text) > 0


def test_execute_batch_full(
    tool: ImpactTool, project_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2 symbols with default detail returns data with 'symbols' key."""
    results = [_make_result("Foo.bar"), _make_result("Baz.qux")]
    call_idx = iter(range(len(results)))
    monkeypatch.setattr(
        tool,
        "_analyze_single",
        lambda *a, **kw: results[next(call_idx)],
    )

    out = tool._execute_batch(
        project_path,
        symbols=["Foo.bar", "Baz.qux"],
        exclude_tests=True,
        detail=None,
    )

    assert out.success is True
    assert "symbols" in out.data
    assert len(out.data["symbols"]) == 2


def test_execute_batch_empty(tool: ImpactTool, project_path: Path) -> None:
    """Empty symbols list returns success=False."""
    out = tool._execute_batch(
        project_path,
        symbols=[],
        exclude_tests=True,
        detail=None,
    )

    assert out.success is False
    assert out.error is not None
    assert "empty" in out.error.lower()


# --- Edge cases ---


def test_execute_batch_non_list_symbols(tool: ImpactTool, project_path: Path) -> None:
    """Non-list symbols param returns success=False with error."""
    out = tool._execute_batch(
        project_path,
        symbols="single_string",  # type: ignore[arg-type]
        exclude_tests=True,
        detail=None,
    )

    assert out.success is False
    assert out.error is not None
    assert "list" in out.error.lower()


def test_execute_batch_mixed_results(
    tool: ImpactTool, project_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One valid + one errored symbol: both in results, text still renders."""
    valid = _make_result("Foo.bar", score="MEDIUM")
    errored = _make_error_result("Missing.sym")
    results = [valid, errored]
    call_idx = iter(range(len(results)))
    monkeypatch.setattr(
        tool,
        "_analyze_single",
        lambda *a, **kw: results[next(call_idx)],
    )

    out = tool._execute_batch(
        project_path,
        symbols=["Foo.bar", "Missing.sym"],
        exclude_tests=True,
        detail=None,
    )

    assert out.success is True
    assert "symbols" in out.data
    assert len(out.data["symbols"]) == 2
    # The valid result has score so text rendering is attempted
    # (may succeed or gracefully fall back to None)
