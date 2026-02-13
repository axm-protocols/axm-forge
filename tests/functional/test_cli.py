"""Functional tests for CLI — end-to-end flows."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from axm_init.cli import app

# Required args for scaffold
SCAFFOLD_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]


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


class TestScaffoldFlow:
    """End-to-end tests for the scaffold command."""

    def test_full_scaffold_creates_project(self, tmp_path: Path) -> None:
        """scaffold creates a project directory with expected files."""
        output, code = _run(
            [
                "scaffold",
                str(tmp_path),
                "--name",
                "my-project",
                *SCAFFOLD_ARGS,
            ]
        )
        assert code == 0
        assert "my-project" in output
        assert "✅" in output

    def test_scaffold_then_check_structure(self, tmp_path: Path) -> None:
        """scaffold creates expected scaffolding structure."""
        _output, code = _run(
            [
                "scaffold",
                str(tmp_path),
                "--name",
                "scaffold-test",
                *SCAFFOLD_ARGS,
            ]
        )
        assert code == 0

        # Copier may create files at target level or in a subdirectory
        # Check that at least a pyproject.toml exists somewhere
        pyproject_files = list(tmp_path.rglob("pyproject.toml"))
        assert len(pyproject_files) > 0, "No pyproject.toml found in scaffolded output"

    def test_scaffold_json_output_is_valid_json(self, tmp_path: Path) -> None:
        """--json flag produces valid, parseable JSON output."""
        output, code = _run(
            [
                "scaffold",
                str(tmp_path),
                "--name",
                "json-test",
                "--json",
                *SCAFFOLD_ARGS,
            ]
        )
        assert code == 0
        data = json.loads(output)
        assert "success" in data
        assert data["success"] is True
        assert "files" in data

    def test_scaffold_with_description(self, tmp_path: Path) -> None:
        """--description flag passes description to template."""
        _output, code = _run(
            [
                "scaffold",
                str(tmp_path),
                "--name",
                "desc-test",
                "--description",
                "My custom description",
                *SCAFFOLD_ARGS,
            ]
        )
        assert code == 0

    def test_scaffold_with_license_flag(self, tmp_path: Path) -> None:
        """--license flag is accepted."""
        _output, code = _run(
            [
                "scaffold",
                str(tmp_path),
                "--name",
                "lic-test",
                "--license",
                "Apache-2.0",
                *SCAFFOLD_ARGS,
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
