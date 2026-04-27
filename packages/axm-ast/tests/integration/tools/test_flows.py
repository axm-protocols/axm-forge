"""Integration tests for axm_ast.tools.flows.FlowsTool."""

from __future__ import annotations

from pathlib import Path


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


class TestFlowsToolDetail:
    """FlowsTool passes detail param through."""

    def test_flowstool_passes_detail(self, tmp_path: Path) -> None:
        """FlowsTool with detail='source' → steps contain source."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="source")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" in steps[0]
        assert "def main" in steps[0]["source"]

    def test_flowstool_default_no_source(self, tmp_path: Path) -> None:
        """FlowsTool default → steps do not contain source key."""
        from axm_ast.tools.flows import FlowsTool

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main")
        assert result.success
        assert result.data is not None
        steps = result.data["steps"]
        assert len(steps) >= 1
        assert "source" not in steps[0]
