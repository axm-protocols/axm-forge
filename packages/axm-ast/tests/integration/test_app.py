"""Split from ``test_impact.py``."""

import json
from pathlib import Path

import pytest

from axm_ast.cli import app


def _make_project(tmp_path: Path) -> Path:
    """Create a typical project with init, module, and tests."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\nfrom .core import helper\n\n__all__ = ["helper"]\n'
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
        "\n"
        "def _private() -> None:\n"
        '    """Private."""\n'
        "    pass\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\n'
        "def main() -> None:\n"
        '    """Main."""\n'
        "    helper(42)\n"
        "\n"
        "def other() -> None:\n"
        '    """Other."""\n'
        "    helper(99)\n"
    )
    # Tests directory
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        '"""Test core."""\ndef test_helper() -> None:\n    """Test."""\n    helper(1)\n'
    )
    (tests / "test_cli.py").write_text(
        '"""Test CLI."""\ndef test_main() -> None:\n    """Test."""\n    main()\n'
    )
    return pkg


class TestImpactCLI:
    """Test impact CLI command."""

    def test_impact_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI produces all sections."""

        pkg_dir = _make_project(tmp_path)
        with pytest.raises(SystemExit):
            app(["impact", str(pkg_dir), "--symbol", "helper"])
        captured = capsys.readouterr()
        assert "helper" in captured.out
        assert "caller" in captured.out.lower() or "impact" in captured.out.lower()

    def test_impact_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output has all expected fields."""

        from axm_ast.cli import app

        pkg_dir = _make_project(tmp_path)
        with pytest.raises(SystemExit):
            app(["impact", str(pkg_dir), "--symbol", "helper", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "symbol" in data
        assert "callers" in data
        assert "score" in data


class TestCallersCLI:
    """Test the CLI callers command."""

    def test_callers_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI prints caller locations."""

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef target() -> None:\n    """Target."""\n    pass\n'
        )
        (pkg_dir / "user.py").write_text(
            '"""User."""\ndef main() -> None:\n    """Main."""\n    target()\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "target"])
        captured = capsys.readouterr()
        assert "target" in captured.out

    def test_callers_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI --json returns structured list."""

        from axm_ast.cli import app

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef target() -> None:\n    """Target."""\n    pass\n'
        )
        (pkg_dir / "user.py").write_text(
            '"""User."""\ndef main() -> None:\n    """Main."""\n    target()\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "target", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["symbol"] == "target"

    def test_callers_no_results(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Symbol with no callers prints message."""

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "lonely"])
        captured = capsys.readouterr()
        assert "no callers" in captured.out.lower() or "0" in captured.out
