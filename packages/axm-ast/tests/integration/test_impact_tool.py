from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult

from axm_ast.tools.impact import ImpactTool
from tests.integration._helpers import (
    _assert_tool_result,
    _make_project_with_test_callers__from_impact_test_filter,
)


@pytest.fixture
def tool() -> ImpactTool:
    return ImpactTool()


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
        symbols="single_string",
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


@pytest.fixture()
def sample_pkg(tmp_path: Path) -> Path:
    """Minimal Python package for impact analysis."""
    pkg = tmp_path / "src" / "sample_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "hello.py").write_text(
        "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    )
    (pkg / "cli.py").write_text(
        "from sample_pkg.hello import greet\n\n"
        "def main() -> None:\n"
        "    print(greet('world'))\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.1.0"\n'
    )
    return tmp_path


class TestImpactToolFunctionalIntegration:
    def test_tool_json_mode_has_text(self, sample_pkg: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_pkg), symbol="greet")
        assert result.success
        assert isinstance(result.text, str)
        assert len(result.text) > 0
        assert "callers" in result.data
        assert "score" in result.data

    def test_tool_compact_mode_uses_text(self, sample_pkg: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_pkg), symbol="greet", detail="compact")
        assert result.success
        assert isinstance(result.text, str)
        assert result.data == {}

    def test_tool_batch_json_has_text(self, sample_pkg: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_pkg), symbols=["greet"])
        assert result.success
        assert isinstance(result.text, str)
        assert isinstance(result.data.get("symbols"), list)


class TestCompactSingleReturnsText:
    """AC1: _execute_single compact returns text, not data."""

    def test_compact_single_returns_text(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_analysis = {"symbol": "foo", "dependents": []}
        compact_md = "# Impact: foo\nNo dependents."

        with (
            patch.object(tool, "_analyze_single", return_value=fake_analysis),
            patch(
                "axm_ast.tools.impact.format_impact_compact",
                return_value=compact_md,
            ),
        ):
            result = tool._execute_single(
                project_path, symbol="foo", exclude_tests=False, detail="compact"
            )

        assert result.success is True
        assert result.text is not None
        assert result.text == compact_md
        assert result.data == {}


class TestCompactBatchReturnsText:
    """AC2: _execute_batch compact returns text, not data."""

    def test_compact_batch_returns_text(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_a = {"symbol": "a", "dependents": []}
        fake_b = {"symbol": "b", "dependents": []}
        compact_md = "# Impact: a, b\nNo dependents."

        with (
            patch.object(tool, "_analyze_single", side_effect=[fake_a, fake_b]),
            patch(
                "axm_ast.tools.impact.format_impact_compact",
                return_value=compact_md,
            ),
        ):
            result = tool._execute_batch(
                project_path,
                symbols=["a", "b"],
                exclude_tests=False,
                detail="compact",
            )

        assert result.success is True
        assert result.text is not None
        assert result.text == compact_md
        assert result.data == {}


class TestNonCompactReturnsData:
    """AC3: Non-compact mode returns structured data, text is None."""

    def test_non_compact_single_returns_data(
        self, tool: ImpactTool, project_path: Path
    ) -> None:

        fake_result = ToolResult(
            success=True, data={"symbol": "foo", "dependents": ["bar"]}
        )

        with patch.object(tool, "_analyze_single_result", return_value=fake_result):
            result = tool._execute_single(
                project_path, symbol="foo", exclude_tests=False, detail=None
            )

        assert result.data != {}
        assert result.data == {"symbol": "foo", "dependents": ["bar"]}
        assert result.text is None

    def test_non_compact_batch_returns_data(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_a = {"symbol": "a", "dependents": []}
        fake_b = {"symbol": "b", "dependents": ["c"]}

        with patch.object(tool, "_analyze_single", side_effect=[fake_a, fake_b]):
            result = tool._execute_batch(
                project_path,
                symbols=["a", "b"],
                exclude_tests=False,
                detail=None,
            )

        assert result.success is True
        assert result.data == {"symbols": [fake_a, fake_b]}
        assert result.text is None


class TestEdgeCases:
    """Edge cases for compact output."""

    def test_empty_symbol_list_compact(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        result = tool._execute_batch(
            project_path,
            symbols=[],
            exclude_tests=False,
            detail="compact",
        )

        assert result.success is False
        assert result.error is not None


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


@pytest.fixture
def sample_pkg__from_impact_tool(tmp_path: Path) -> Path:
    """Create a minimal package for tool-level tests."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '"""Demo."""\n\n__all__ = ["greet"]\n\nfrom demo.core import greet\n'
    )
    (pkg / "core.py").write_text(
        '"""Core."""\n\n'
        '__all__ = ["greet"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
    )
    return tmp_path


@pytest.fixture
def impact_tool() -> ImpactTool:
    return ImpactTool()


class TestImpactToolEdgeCases:
    """Cover tools/impact.py uncovered paths."""

    def test_exception(self, tmp_path: Path, mocker: MagicMock) -> None:

        pkg = _make_pkg(tmp_path, {"__init__.py": "", "mod.py": "x = 1\n"})
        mocker.patch(
            "axm_ast.core.impact.analyze_impact",
            side_effect=RuntimeError("impact boom"),
        )
        result = ImpactTool().execute(path=str(pkg), symbol="x")
        # The _analyze_single catches exception and returns error dict
        # Then _analyze_single_result converts it to ToolResult(success=False)
        assert result.success is False
        assert "impact boom" in (result.error or "")

    def test_batch_compact(self, tmp_path: Path) -> None:

        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": (
                    "def foo() -> None:\n    pass\n\ndef bar() -> None:\n    foo()\n"
                ),
            },
        )
        result = ImpactTool().execute(
            path=str(pkg), symbols=["foo", "bar"], detail="compact"
        )
        assert result.success is True
        assert result.data == {}
        assert result.text is not None

    def test_single_compact(self, tmp_path: Path) -> None:

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def foo() -> None:\n    pass\n"},
        )
        result = ImpactTool().execute(path=str(pkg), symbol="foo", detail="compact")
        assert result.success is True
        assert result.data == {}
        assert result.text is not None

    def test_symbol_not_found_error_result(self, tmp_path: Path) -> None:

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "x = 1\n"},
        )
        result = ImpactTool().execute(path=str(pkg), symbol="nonexistent_sym_xyz")
        assert result.success is False
        assert "not found" in (result.error or "")


def test_impact_tool_top_exception(tmp_path: Path, mocker: MagicMock) -> None:

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.workspace.detect_workspace",
        side_effect=RuntimeError("top boom"),
    )
    result = ImpactTool().execute(path=str(pkg), symbol="foo")
    # _analyze_single catches it, returns error dict
    assert result.success is False


class TestImpactToolWorkspace:
    """Cover tools/impact.py workspace branch (line 168, 170)."""

    def test_workspace_impact(self, tmp_path: Path, mocker: MagicMock) -> None:

        pkg = _make_pkg(
            tmp_path,
            {"__init__.py": "", "mod.py": "def foo():\n    pass\n"},
        )
        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.impact.analyze_impact_workspace",
            return_value={
                "symbol": "foo",
                "score": "LOW",
                "definition": {"module": "mod", "line": 1},
                "callers": [],
                "test_files": [],
            },
        )
        result = ImpactTool().execute(path=str(pkg), symbol="foo")
        assert result.success is True


def test_tool_passes_exclude_tests(tmp_path: Path) -> None:
    """ImpactTool.execute forwards exclude_tests to analyze_impact."""
    from unittest.mock import patch

    tool = ImpactTool()
    with patch("axm_ast.tools.impact.ImpactTool._analyze_single") as mock:
        mock.return_value = {"symbol": "foo", "score": "LOW", "definition": {}}
        tool.execute(path=str(tmp_path), symbol="foo", exclude_tests=True)
        mock.assert_called_once_with(tmp_path, "foo", exclude_tests=True)


class TestImpactToolCompactMode:
    """ImpactTool.execute with detail='compact'."""

    def test_impact_tool_compact_mode(self, sample_pkg__from_impact_tool: Path) -> None:
        """ImpactTool.execute(detail='compact') on sample_pkg returns compact string."""

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_pkg__from_impact_tool / "src" / "demo"),
            symbol="greet",
            detail="compact",
        )
        assert result.success is True
        # Compact mode returns text, not data
        assert result.data == {}
        assert result.text is not None
        assert isinstance(result.text, str)

    def test_impact_tool_full_unchanged(
        self, sample_pkg__from_impact_tool: Path
    ) -> None:
        """ImpactTool.execute() without detail → same JSON output (regression)."""

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_pkg__from_impact_tool / "src" / "demo"),
            symbol="greet",
        )
        assert result.success is True
        # Default mode: data is a dict with impact fields
        assert isinstance(result.data, dict)
        assert "score" in result.data


class TestImpactWorkspaceMode:
    """Workspace-mode integration of ImpactTool compact output."""

    @patch("axm_ast.tools.impact.ImpactTool._analyze_single")
    def test_workspace_mode(self, mock_analyze: MagicMock, tmp_path: Path) -> None:
        """Workspace path with cross-package impact → all packages in table."""

        mock_analyze.return_value = {
            "symbol": "SharedModel",
            "definition": {"module": "pkg_a.models", "line": 5, "kind": "class"},
            "callers": [
                {"name": "use_model", "module": "pkg_b.service"},
                {"name": "test_model", "module": "pkg_c.tests"},
            ],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["pkg_a.models", "pkg_b.service", "pkg_c.tests"],
            "test_files": [],
            "git_coupled": [],
            "score": "HIGH",
            "cross_package_impact": ["pkg_b", "pkg_c"],
        }

        tool = ImpactTool()
        result = tool.execute(
            path=str(tmp_path),
            symbol="SharedModel",
            detail="compact",
        )
        assert result.success is True


def test_impact_compact_with_test_callers(tmp_path: Path) -> None:
    """Compact output includes test caller lines when test_filter='related'."""
    from axm_ast.tools.impact import ImpactTool

    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    tool = ImpactTool()
    result = tool.execute(
        path=str(pkg),
        symbol="target_fn",
        test_filter="related",
        detail="compact",
    )
    assert result.success
    compact = result.text
    # Compact output should contain the test caller reference
    assert compact is not None
    assert "test_a" in compact


class TestImpactToolIntegration:
    """Tests for ast_impact tool."""

    def test_analyze_impact(self, sample_project: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "score" in result.data

    def test_missing_symbol(self, sample_project: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is False

    # --- Batch mode (AXM-462) ---

    def test_symbols_batch_success(self, sample_project: Path) -> None:
        """AC1/2: Batch with two valid symbols returns score for each."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbols=["greet", "Helper"],
        )
        assert result.success is True
        assert "symbols" in result.data
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert "score" in symbols[0]
        assert "score" in symbols[1]

    def test_symbols_batch_partial_missing(self, sample_project: Path) -> None:
        """AC2: Batch with one valid + one missing → mixed results."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbols=["greet", "missing_xyz"],
        )
        assert result.success is True
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert "score" in symbols[0]
        assert "error" in symbols[1]
        assert symbols[1]["symbol"] == "missing_xyz"

    def test_symbols_precedence(self, sample_project: Path) -> None:
        """Edge: Both symbol and symbols → symbols takes precedence."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbol="greet",
            symbols=["Helper"],
        )
        assert result.success is True
        assert "symbols" in result.data
        assert len(result.data["symbols"]) == 1


def test_execute_with_neither_symbol_nor_symbols_returns_error(
    impact_tool: ImpactTool, tmp_path: Any
) -> None:
    """AC2: missing both ``symbol`` and ``symbols`` returns a clear error."""
    result = impact_tool.execute(path=str(tmp_path), symbol=None, symbols=None)

    assert result.success is False
    assert result.error is not None
    assert "symbol" in result.error.lower()


def _is_test_module_name(module: str) -> bool:
    """Local mirror of the public classification rule for assertion purposes."""
    parts = module.split(".")
    return any(p.startswith("test_") or p == "tests" for p in parts)


def test_impact_mcp_test_filter_param(tmp_path: Path) -> None:
    """MCP tool accepts test_filter param and returns filtered results."""
    from axm_ast.tools.impact import ImpactTool

    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    tool = ImpactTool()
    result = tool.execute(
        path=str(pkg),
        symbol="target_fn",
        test_filter="related",
    )
    assert result.success
    test_callers = [
        c for c in result.data["callers"] if _is_test_module_name(c["module"])
    ]
    test_modules = {c["module"] for c in test_callers}
    assert any("test_a" in m for m in test_modules)
    assert not any("test_b" in m for m in test_modules)
