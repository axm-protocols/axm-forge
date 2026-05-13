from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


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
