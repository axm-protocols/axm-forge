from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_ast.hooks.impact import ImpactHook


@pytest.fixture
def hook() -> ImpactHook:
    return ImpactHook()


@pytest.fixture
def fake_report() -> dict[str, Any]:
    return {
        "symbol": "foo",
        "score": "MEDIUM",
        "callers": [],
        "tests": [],
        "git_coupled": [],
        "cross_package": [],
        "definition": {"file": "foo.py", "line": 1, "kind": "function"},
    }


# --- Unit tests ---


def test_single_symbol_has_text(
    hook: ImpactHook,
    fake_report: dict[str, Any],
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Single-symbol default detail -> result.text starts with 'ast_impact |'."""
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo", ["foo"], False, "full"),
    )
    mocker.patch("axm_ast.core.impact.analyze_impact", return_value=fake_report)
    mocker.patch("axm_ast.hooks.impact._enrich_report", return_value=fake_report)

    result = hook.execute({})

    assert result.success is True
    assert result.text is not None
    assert result.text.startswith("ast_impact |")
    assert result.metadata["impact"] is not None


def test_multi_symbol_has_text(
    hook: ImpactHook,
    fake_report: dict[str, Any],
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Multi-symbol default detail -> result.text has section headers."""
    report2 = {**fake_report, "symbol": "bar", "score": "HIGH"}
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo\nbar", ["foo", "bar"], False, "full"),
    )
    mocker.patch(
        "axm_ast.core.impact.analyze_impact",
        side_effect=[fake_report, report2],
    )
    merged = {**fake_report, "symbol": "foo\nbar", "callers": [], "tests": []}
    mocker.patch("axm_ast.hooks.impact._merge_impact_reports", return_value=merged)
    mocker.patch("axm_ast.hooks.impact._enrich_report", return_value=merged)

    result = hook.execute({})

    assert result.success is True
    assert result.text is not None
    assert result.text.startswith("ast_impact |")
    assert "## " in result.text
    assert result.metadata["impact"] is not None


def test_compact_mode_no_text(
    hook: ImpactHook,
    fake_report: dict[str, Any],
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Compact mode -> result.text is None (text goes in impact metadata)."""
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo", ["foo"], False, "compact"),
    )
    mocker.patch("axm_ast.core.impact.analyze_impact", return_value=fake_report)
    mocker.patch(
        "axm_ast.tools.impact.format_impact_compact",
        return_value="compact-text",
    )

    result = hook.execute({})

    assert result.success is True
    assert result.text is None


# --- Edge cases ---


def test_analyze_impact_raises(
    hook: ImpactHook,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """analyze_impact raises -> HookResult.fail, no text."""
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo", ["foo"], False, "full"),
    )
    mocker.patch(
        "axm_ast.core.impact.analyze_impact",
        side_effect=ValueError("symbol not found"),
    )

    result = hook.execute({})

    assert result.success is False
    assert not result.text


def test_report_with_error_key(
    hook: ImpactHook,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Report containing 'error' key -> render_impact_text handles it."""
    error_report: dict[str, Any] = {
        "error": "could not resolve symbol",
        "symbol": "foo",
    }
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo", ["foo"], False, "full"),
    )
    mocker.patch("axm_ast.core.impact.analyze_impact", return_value=error_report)
    mocker.patch("axm_ast.hooks.impact._enrich_report", return_value=error_report)

    result = hook.execute({})

    assert result.text is not None
    assert "error" in result.text.lower()


def test_empty_callers_tests(
    hook: ImpactHook,
    fake_report: dict[str, Any],
    tmp_path: Path,
    mocker: Any,
) -> None:
    """Report with empty callers/tests -> text still renders."""
    mocker.patch(
        "axm_ast.hooks.impact._parse_impact_params",
        return_value=(tmp_path, "foo", ["foo"], False, "full"),
    )
    mocker.patch("axm_ast.core.impact.analyze_impact", return_value=fake_report)
    mocker.patch("axm_ast.hooks.impact._enrich_report", return_value=fake_report)

    result = hook.execute({})

    assert result.success is True
    assert result.text is not None
    assert len(result.text) > 0
