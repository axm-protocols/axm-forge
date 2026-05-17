"""E2E tests for axm-ast CLI commands (subprocess black-box)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a temporary Python package from file name → content mapping."""
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestCalleesCLI:
    """CLI callees command integration tests."""

    def test_callees_json_output(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        result = subprocess.run(
            [
                "uv",
                "run",
                "axm-ast",
                "callees",
                str(pkg_path),
                "--symbol",
                "main",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        symbols = [c["symbol"] for c in data]
        assert "helper" in symbols

    def test_callees_no_results(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": "def noop():\n    x = 42\n",
            },
        )
        result = subprocess.run(
            ["uv", "run", "axm-ast", "callees", str(pkg_path), "--symbol", "noop"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
        )
        assert result.returncode == 0
        assert "No callees" in result.stdout or "📭" in result.stdout
