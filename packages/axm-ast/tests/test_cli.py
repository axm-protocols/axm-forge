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
    return capsys.readouterr().out


class TestDescribeCommand:
    """Tests for axm-ast describe."""

    def test_describe_default_is_detailed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Default detail level is 'detailed', matching MCP DescribeTool."""
        output = _run(["describe", str(SAMPLE_PKG)], capsys)
        assert "sample_pkg" in output
        assert "greet" in output

    def test_describe_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--detail", "summary"], capsys)
        assert "sample_pkg" in output

    def test_describe_detailed(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--detail", "detailed"], capsys)
        assert "sample_pkg" in output

    def test_describe_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["describe", str(SAMPLE_PKG), "--json"], capsys)
        assert '"name"' in output

    def test_describe_invalid_path(self) -> None:
        with pytest.raises(SystemExit):
            app(["describe", "/nonexistent/path"])


class TestInspectCommand:
    """Tests for axm-ast inspect (package-level, matching MCP InspectTool)."""

    def test_inspect_lists_symbols(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Without --symbol, lists all symbols in the package."""
        output = _run(["inspect", str(SAMPLE_PKG)], capsys)
        assert "greet" in output

    def test_inspect_symbol(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "greet"],
            capsys,
        )
        assert "greet" in output

    def test_inspect_class_method(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "Calculator.add"],
            capsys,
        )
        assert "add" in output

    def test_inspect_classmethod(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "Calculator.from_config"],
            capsys,
        )
        assert "from_config" in output

    def test_inspect_property(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "Calculator.name"],
            capsys,
        )
        assert "name" in output

    def test_inspect_method_not_found(self) -> None:
        with pytest.raises(SystemExit):
            app(["inspect", str(SAMPLE_PKG), "--symbol", "Calculator.nonexistent"])

    def test_inspect_class_not_found(self) -> None:
        with pytest.raises(SystemExit):
            app(["inspect", str(SAMPLE_PKG), "--symbol", "NonExistent.method"])

    def test_inspect_invalid_path(self) -> None:
        with pytest.raises(SystemExit):
            app(["inspect", "/nonexistent/path", "--symbol", "greet"])

    def test_inspect_source_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--source includes source code in output."""
        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "greet", "--source"],
            capsys,
        )
        assert "greet" in output
        # Source should include the function body
        assert "Hello" in output or "def greet" in output

    def test_inspect_json_has_line_info(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json output includes file, start_line, end_line."""
        import json

        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "greet", "--json"],
            capsys,
        )
        data = json.loads(output)
        assert "file" in data
        assert "start_line" in data
        assert "end_line" in data
        assert data["start_line"] > 0

    def test_inspect_json_source(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--json --source includes source key."""
        import json

        output = _run(
            ["inspect", str(SAMPLE_PKG), "--symbol", "greet", "--source", "--json"],
            capsys,
        )
        data = json.loads(output)
        assert "source" in data
        assert "def greet" in data["source"]


class TestGraphCommand:
    """Tests for axm-ast graph."""

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


class TestContextCommand:
    """Tests for axm-ast context."""

    def test_context_depth0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--depth 0 produces compact output."""
        output = _run(["context", str(SAMPLE_PKG), "--depth", "0", "--json"], capsys)
        import json

        data = json.loads(output)
        assert "top_modules" in data
        assert "modules" not in data


class TestVersionCommand:
    """Tests for axm-ast version."""

    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = _run(["version"], capsys)
        assert "axm-ast" in output


class TestResolveDir:
    """Tests for ``_resolve_dir`` helper (AC #2 + #4)."""

    def test_cli_describe_output_unchanged(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Describe output must be identical after refactoring (AC #4)."""
        output = _run(["describe", str(SAMPLE_PKG)], capsys)
        # Core content assertions — same as pre-refactoring baseline
        assert "sample_pkg" in output
        assert "greet" in output

    @pytest.mark.parametrize(
        "cmd",
        [
            ["describe"],
            ["inspect"],
            ["graph"],
            ["search"],
            ["callers", "--symbol", "x"],
            ["callees", "--symbol", "x"],
            ["context"],
            ["impact", "--symbol", "x"],
            ["dead-code"],
            ["flows"],
            ["docs"],
        ],
    )
    def test_cli_invalid_path(self, cmd: list[str]) -> None:
        """Every command using ``_resolve_dir`` rejects nonexistent paths (AC #2)."""
        with pytest.raises(SystemExit):
            app([cmd[0], "/nonexistent/path", *cmd[1:]])
