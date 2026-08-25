from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_ast.core.docs import discover_docs

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestCliDocs:
    """Functional tests for the CLI docs command."""

    def test_cli_docs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI docs --json outputs valid JSON."""
        from axm_ast.cli import app

        with pytest.raises(SystemExit, match="0"):
            app(["docs", str(FIXTURES / "sample_pkg" / ".."), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "pages" in data

    def test_cli_docs_dogfood(self) -> None:
        """Dogfood: discover_docs works on axm-ast project root."""
        project_root = Path(__file__).parent.parent.parent.parent
        result = discover_docs(project_root)
        assert result["readme"] is not None
        assert "axm-ast" in result["readme"]["content"]
        assert result["mkdocs"] is not None
        assert len(result["pages"]) >= 1
