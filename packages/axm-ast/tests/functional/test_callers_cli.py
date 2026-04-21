"""Functional tests for the callers CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.functional


class TestCallersCLI:
    """Test the CLI callers command."""

    def test_callers_text_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI prints caller locations."""
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
            app(["callers", str(pkg_dir), "--symbol", "target"])
        captured = capsys.readouterr()
        assert "target" in captured.out

    def test_callers_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI --json returns structured list."""
        import json

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
        from axm_ast.cli import app

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
        )
        with pytest.raises(SystemExit):
            app(["callers", str(pkg_dir), "--symbol", "lonely"])
        captured = capsys.readouterr()
        assert "no callers" in captured.out.lower() or "0" in captured.out
