"""Functional tests for CLI — end-to-end flows."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from axm_init.cli import app


def _run(args: list[str]) -> tuple[str, int]:
    """Run CLI and capture stdout + exit code."""
    f = io.StringIO()
    code = 0
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return f.getvalue(), code


class TestInitFlow:
    """End-to-end tests for the init command."""

    def test_full_init_creates_project(self, tmp_path: Path) -> None:
        """init creates a project directory with expected files."""
        output, code = _run(["init", str(tmp_path), "--name", "my-project"])
        assert code == 0
        assert "my-project" in output
        assert "✅" in output

    def test_init_then_check_structure(self, tmp_path: Path) -> None:
        """init creates expected scaffolding structure."""
        _output, code = _run(["init", str(tmp_path), "--name", "scaffold-test"])
        assert code == 0

        # Copier may create files at target level or in a subdirectory
        # Check that at least a pyproject.toml exists somewhere
        pyproject_files = list(tmp_path.rglob("pyproject.toml"))
        assert len(pyproject_files) > 0, "No pyproject.toml found in scaffolded output"

    def test_init_json_output_is_valid_json(self, tmp_path: Path) -> None:
        """--json flag produces valid, parseable JSON output."""
        output, code = _run(["init", str(tmp_path), "--name", "json-test", "--json"])
        assert code == 0
        data = json.loads(output)
        assert "success" in data
        assert data["success"] is True
        assert "files" in data

    def test_init_with_description(self, tmp_path: Path) -> None:
        """--description flag passes description to template."""
        _output, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "desc-test",
                "--description",
                "My custom description",
            ]
        )
        assert code == 0

    def test_init_different_templates(self, tmp_path: Path) -> None:
        """init with an explicit template works."""
        _output, code = _run(
            [
                "init",
                str(tmp_path),
                "--name",
                "tmpl-test",
                "--template",
                "minimal",
            ]
        )
        assert code == 0


class TestVersionFlow:
    """End-to-end test for version command."""

    def test_version_returns_valid_output(self) -> None:
        """version command produces clean output."""
        output, code = _run(["version"])
        assert code == 0
        output = output.strip()
        assert output.startswith("axm-init ")
        # Should not contain error messages
        assert "Error" not in output
        assert "Traceback" not in output
