"""Split from ``test_hooks.py``."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.impact import ImpactHook


class TestImpactHookExecuteIntegration:
    """Tests for ImpactHook — single and multi-symbol analysis."""

    @patch("axm_ast.core.impact.analyze_impact")
    def test_single_symbol(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Single symbol — passes through directly, no merge."""

        mock_impact.return_value = {
            "symbol": "Foo",
            "definition": {"file": "foo.py", "line": 10},
            "callers": [{"name": "bar", "file": "bar.py"}],
            "type_refs": [],
            "reexports": [],
            "affected_modules": ["mod_a"],
            "test_files": ["test_foo.py"],
            "git_coupled": [],
            "score": "MEDIUM",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="Foo", path=str(tmp_path))

        assert result.success
        mock_impact.assert_called_once_with(
            tmp_path, "Foo", project_root=tmp_path.parent, exclude_tests=False
        )
        assert result.metadata["impact"]["score"] == "MEDIUM"

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_newline_split(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Newline-separated symbols are split and each analyzed."""

        mock_impact.return_value = {
            "symbol": "X",
            "definition": {"file": "x.py", "line": 1},
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        assert mock_impact.call_count == 2
        calls = [c.args for c in mock_impact.call_args_list]
        assert calls[0] == (tmp_path, "A")
        assert calls[1] == (tmp_path, "B")

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_max_score(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Merged score takes the maximum across all symbols."""

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            base: dict[str, Any] = {
                "definition": None,
                "callers": [],
                "type_refs": [],
                "reexports": [],
                "affected_modules": [],
                "test_files": [],
                "git_coupled": [],
            }
            if sym == "A":
                return {**base, "symbol": "A", "score": "LOW"}
            return {**base, "symbol": "B", "score": "HIGH"}

        mock_impact.side_effect = side_effect

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        assert result.metadata["impact"]["score"] == "HIGH"

    @patch("axm_ast.core.impact.analyze_impact")
    def test_multi_symbol_dedup_modules(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Affected modules and test files are deduplicated."""

        base: dict[str, Any] = {
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "git_coupled": [],
            "score": "LOW",
        }
        mock_impact.return_value = {
            **base,
            "symbol": "X",
            "affected_modules": ["mod_a", "mod_b"],
            "test_files": ["test_x.py"],
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\nB", path=str(tmp_path))

        assert result.success
        impact = result.metadata["impact"]
        # Both returns identical modules — should be deduplicated
        assert impact["affected_modules"] == ["mod_a", "mod_b"]
        assert impact["test_files"] == ["test_x.py"]

    @patch("axm_ast.core.impact.analyze_impact")
    def test_whitespace_handling(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty lines and trailing whitespace are ignored."""

        mock_impact.return_value = {
            "symbol": "X",
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
        }

        hook = ImpactHook()
        result = hook.execute({}, symbol="A\n  \nB\n", path=str(tmp_path))

        assert result.success
        # Only A and B should be analyzed, not empty strings
        assert mock_impact.call_count == 2


def _make_impact_dict(
    symbol: str = "greet",
    *,
    callers: list[dict[str, Any]] | None = None,
    test_files: list[str] | None = None,
    definition: dict[str, Any] | None = None,
    score: str = "MEDIUM",
) -> dict[str, Any]:
    """Build a realistic impact analysis dict."""
    return {
        "symbol": symbol,
        "definition": definition
        or {"module": "demo.core", "line": 10, "kind": "function"},
        "callers": callers or [],
        "type_refs": [],
        "reexports": [],
        "affected_modules": ["demo.core", "demo.cli"],
        "test_files": test_files or [],
        "git_coupled": [],
        "score": score,
    }


class TestImpactHookCompact:
    """ImpactHook with detail='compact'."""

    @patch("axm_ast.core.impact.analyze_impact")
    def test_impact_hook_compact_single(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Single symbol, detail=compact → compact markdown."""

        mock_impact.return_value = _make_impact_dict(
            symbol="Foo",
            callers=[{"name": "bar", "module": "mod_b"}],
        )

        hook = ImpactHook()
        result = hook.execute(
            {},
            symbol="Foo",
            path=str(tmp_path),
            detail="compact",
        )

        assert result.success
        # Compact mode should produce markdown string in metadata
        impact_data = result.metadata.get("impact")
        assert impact_data is not None
        assert isinstance(impact_data, str)
        assert "Foo" in impact_data

    @patch("axm_ast.core.impact.analyze_impact")
    def test_impact_hook_compact_multi(
        self,
        mock_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """ImpactHook with 3 symbols, detail=compact → merged compact table."""

        def side_effect(_path: Path, sym: str, **_kw: object) -> dict[str, Any]:
            return _make_impact_dict(
                symbol=sym,
                callers=[{"name": f"caller_{sym}", "module": f"mod_{sym}"}],
            )

        mock_impact.side_effect = side_effect

        hook = ImpactHook()
        result = hook.execute(
            {},
            symbol="A\nB\nC",
            path=str(tmp_path),
            detail="compact",
        )

        assert result.success
        impact_data = result.metadata.get("impact")
        assert isinstance(impact_data, str)
        # All three symbols should appear in the merged compact output
        assert "A" in impact_data
        assert "B" in impact_data
        assert "C" in impact_data


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


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


class TestImpactHook:
    """ImpactHook execution tests."""

    def test_impact_hook_execute(self, tmp_path: Path) -> None:
        """Valid path + symbol → HookResult.ok with impact data."""
        from axm_ast.hooks.impact import ImpactHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def helper():\n    return 42\n\ndef main():\n    helper()\n"
                ),
            },
        )
        hook = ImpactHook()
        result = hook.execute({"working_dir": str(pkg_path)}, symbol="helper")
        assert result.success
        assert "impact" in result.metadata
        impact = result.metadata["impact"]
        assert "symbol" in impact
        assert impact["symbol"] == "helper"

    def test_impact_hook_no_symbol(self) -> None:
        """Missing symbol param → HookResult.fail."""
        from axm_ast.hooks.impact import ImpactHook

        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert "symbol" in (result.error or "").lower()

    def test_impact_hook_path_param(self, tmp_path: Path) -> None:
        """path param overrides working_dir from context."""
        from axm_ast.hooks.impact import ImpactHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = ImpactHook()
        result = hook.execute(
            {"working_dir": "/nonexistent"},
            symbol="main",
            path=str(pkg_path),
        )
        assert result.success
        assert "impact" in result.metadata
