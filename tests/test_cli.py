"""Test CLI commands — integration tests.

Cyclopts calls sys.exit(0) on success, so we catch SystemExit(0) here.
"""

from pathlib import Path

import pytest

from axm_ast.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


def _run(args: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    """Run CLI and return captured stdout."""
    try:
        app(args)
    except SystemExit as e:
        if e.code != 0:
            raise
    return capsys.readouterr().out  # type: ignore[no-any-return]


class TestDescribeCommand:
    """Tests for axm-ast describe."""

    def test_describe_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG)], capsys)
        assert "sample_pkg" in output
        assert "greet" in output

    def test_describe_detailed(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--detail", "detailed"], capsys)
        assert "sample_pkg" in output

    def test_describe_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--json"], capsys)
        assert '"name"' in output

    def test_describe_with_budget(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--budget", "5"], capsys)
        assert isinstance(output, str)

    def test_describe_invalid_path(self) -> None:
        with pytest.raises(SystemExit):
            app(["describe", "/nonexistent/path"])


class TestInspectCommand:
    """Tests for axm-ast inspect."""

    def test_inspect_module(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["inspect", str(SAMPLE_PKG / "__init__.py")], capsys)
        assert "greet" in output

    def test_inspect_symbol(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            [
                "inspect",
                str(SAMPLE_PKG / "__init__.py"),
                "--symbol",
                "greet",
            ],
            capsys,
        )
        assert "greet" in output

    def test_inspect_invalid_path(self) -> None:
        with pytest.raises(SystemExit):
            app(["inspect", "/nonexistent.py"])


class TestGraphCommand:
    """Tests for axm-ast graph."""

    def test_graph_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["graph", str(SAMPLE_PKG)], capsys)
        assert isinstance(output, str)

    def test_graph_mermaid(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["graph", str(SAMPLE_PKG), "--format", "mermaid"], capsys)
        assert "graph" in output or "flowchart" in output

    def test_graph_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["graph", str(SAMPLE_PKG), "--json"], capsys)
        assert "{" in output


class TestSearchCommand:
    """Tests for axm-ast search."""

    def test_search_by_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["search", str(SAMPLE_PKG), "--name", "greet"], capsys)
        assert "greet" in output

    def test_search_by_returns(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["search", str(SAMPLE_PKG), "--returns", "str"], capsys)
        assert "greet" in output or "str" in output

    def test_search_no_results(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            ["search", str(SAMPLE_PKG), "--name", "zzz_nonexistent"],
            capsys,
        )
        assert "no results" in output.lower() or output.strip() == ""


class TestStubCommand:
    """Tests for axm-ast stub."""

    def test_stub_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["stub", str(SAMPLE_PKG)], capsys)
        assert "def greet" in output
        assert "class Calculator" in output
        assert "return" not in output


class TestVersionCommand:
    """Tests for axm-ast version."""

    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["version"], capsys)
        assert "axm-ast" in output
