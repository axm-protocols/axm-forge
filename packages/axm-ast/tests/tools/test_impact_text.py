from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_impact_dict(  # noqa: PLR0913
    symbol: str = "foo",
    score: str = "MEDIUM",
    callers: list[dict[str, Any]] | None = None,
    test_files: list[str] | None = None,
    affected_modules: list[str] | None = None,
    definition: dict[str, Any] | None = None,
    git_coupled: list[str] | None = None,
    cross_package_impact: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "symbol": symbol,
        "score": score,
        "callers": callers if callers is not None else [],
        "test_files": test_files if test_files is not None else [],
        "affected_modules": affected_modules if affected_modules is not None else [],
        "definition": definition
        or {"module": "pkg.mod", "line": 10, "kind": "function"},
        "git_coupled": git_coupled if git_coupled is not None else [],
        "type_refs": [],
        "reexports": [],
        "cross_package_impact": cross_package_impact
        if cross_package_impact is not None
        else [],
    }
    d.update(extra)
    return d


# ── Unit: render_impact_text ─────────────────────────────────────────────


class TestRenderImpactText:
    def test_render_impact_text_basic(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report = _make_impact_dict(
            symbol="greet",
            score="HIGH",
            callers=[{"name": "main", "module": "pkg.cli", "line": 5}],
            test_files=["tests/test_hello.py"],
            definition={"module": "pkg.hello", "line": 10, "kind": "function"},
        )
        text = render_impact_text(report)
        assert "greet" in text
        assert "HIGH" in text
        assert "pkg.hello" in text
        assert "10" in text
        assert "main" in text
        assert "test_hello" in text

    def test_render_impact_text_no_callers(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report = _make_impact_dict(symbol="orphan", callers=[])
        text = render_impact_text(report)
        assert "none" in text.lower()

    def test_render_impact_text_no_tests(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report = _make_impact_dict(symbol="untested", test_files=[])
        text = render_impact_text(report)
        assert "none" in text.lower()

    def test_render_impact_text_not_found(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report: dict[str, Any] = {"symbol": "x", "error": "not found"}
        text = render_impact_text(report)
        assert "x" in text
        assert "not found" in text

    def test_render_impact_text_with_signature(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report = _make_impact_dict(
            symbol="greet",
            definition={
                "module": "pkg.hello",
                "line": 10,
                "kind": "function",
                "signature": "def greet(name: str) -> str",
            },
        )
        text = render_impact_text(report)
        assert "greet" in text
        assert "def greet" in text or "greet(name: str)" in text


# ── Unit: render_impact_batch_text ───────────────────────────────────────


class TestRenderImpactBatchText:
    def test_render_impact_batch_text(self) -> None:
        from axm_ast.tools.impact import render_impact_batch_text

        reports = [
            _make_impact_dict(symbol="a", score="LOW"),
            _make_impact_dict(symbol="b", score="MEDIUM"),
            _make_impact_dict(symbol="c", score="HIGH"),
        ]
        text = render_impact_batch_text(reports)
        assert "3 symbols" in text
        assert "a" in text
        assert "b" in text
        assert "c" in text

    def test_render_impact_batch_text_mixed_scores(self) -> None:
        from axm_ast.tools.impact import render_impact_batch_text

        reports = [
            _make_impact_dict(symbol="lo", score="LOW"),
            _make_impact_dict(symbol="hi", score="HIGH"),
        ]
        text = render_impact_batch_text(reports)
        assert "max=HIGH" in text


# ── Functional: ImpactTool integration ───────────────────────────────────


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


class TestImpactToolFunctional:
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

    def test_verify_enrichment_regression(self, mocker: Any) -> None:
        """JSON mode data dict must retain callers, test_files, score keys."""
        from axm_ast.tools.impact import ImpactTool

        mock_report = _make_impact_dict(
            symbol="greet",
            score="MEDIUM",
            callers=[{"name": "main", "module": "pkg.cli", "line": 5}],
            test_files=["tests/test_hello.py"],
        )
        tool = ImpactTool()
        mocker.patch.object(tool, "_analyze_single", return_value=mock_report)

        result = tool._execute_single(
            project_path=Path("/fake"),
            symbol="greet",
            exclude_tests=False,
            detail=None,
        )
        assert result.success
        assert "callers" in result.data
        assert "test_files" in result.data
        assert "score" in result.data


# ── Edge cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_symbol_not_found_graceful(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report: dict[str, Any] = {
            "symbol": "missing",
            "error": "not found",
            "definition": None,
        }
        text = render_impact_text(report)
        assert "missing" in text
        assert "not found" in text or "error" in text.lower()

    def test_empty_batch(self) -> None:
        from axm_ast.tools.impact import render_impact_batch_text

        text = render_impact_batch_text([])
        assert text == "" or "no symbols" in text.lower() or "0 symbols" in text

    def test_render_crash_fallback(self) -> None:
        """Malformed dict should not crash."""
        from axm_ast.tools.impact import render_impact_text

        report: dict[str, Any] = {"symbol": "broken"}
        try:
            render_impact_text(report)
        except Exception:  # noqa: BLE001
            pytest.fail("render_impact_text should not crash on malformed input")

    def test_cross_package_impact_included(self) -> None:
        from axm_ast.tools.impact import render_impact_text

        report = _make_impact_dict(
            symbol="shared_fn",
            cross_package_impact=[{"package": "other-pkg", "module": "other.mod"}],
        )
        text = render_impact_text(report)
        assert "other" in text.lower() or "cross" in text.lower()
