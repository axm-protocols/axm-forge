"""Integration tests for axm_ast.hooks.impact.ImpactHook."""

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
