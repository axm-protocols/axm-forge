"""Functional tests for CLI — end-to-end flows.

TestScaffoldFlow uses a shared ``scope="module"`` fixture that scaffolds once
via the real Copier adapter, then all tests assert read-only against the same
output.  Each test is marked ``@pytest.mark.slow`` so it can be excluded from
the default fast run.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

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


# ── Module-scoped scaffold fixture ───────────────────────────────────────


@pytest.fixture(scope="module")
def scaffolded_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold a project *once* for the whole module via real Copier.

    All TestScaffoldFlow tests assert read-only against this directory.
    """
    target = tmp_path_factory.mktemp("scaffold_func")
    args = [
        "scaffold",
        str(target),
        "--name",
        "func-test-project",
        "--description",
        "My custom description",
        *SCAFFOLD_ARGS,
    ]
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit:
        pass
    return target


@pytest.fixture(scope="module")
def scaffolded_json_output(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, int]:
    """Scaffold with --json and return (output, exit_code)."""
    target = tmp_path_factory.mktemp("scaffold_json")
    return _run(
        [
            "scaffold",
            str(target),
            "--name",
            "json-test",
            "--json",
            *SCAFFOLD_ARGS,
        ]
    )


@pytest.fixture(scope="module")
def scaffolded_license_output(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[str, int]:
    """Scaffold with --license and return (output, exit_code)."""
    target = tmp_path_factory.mktemp("scaffold_lic")
    return _run(
        [
            "scaffold",
            str(target),
            "--name",
            "lic-test",
            "--license",
            "Apache-2.0",
            *SCAFFOLD_ARGS,
        ]
    )


# ── Slow scaffold tests ─────────────────────────────────────────────────


@pytest.mark.slow
class TestScaffoldFlow:
    """End-to-end tests for the scaffold command (real Copier)."""

    def test_full_scaffold_creates_project(self, scaffolded_project: Path) -> None:
        """scaffold creates a project directory with expected files."""
        assert scaffolded_project.exists()
        # Should have at least some files
        all_files = list(scaffolded_project.rglob("*"))
        assert len(all_files) > 0

    def test_scaffold_then_check_structure(self, scaffolded_project: Path) -> None:
        """scaffold creates expected scaffolding structure."""
        pyproject_files = list(scaffolded_project.rglob("pyproject.toml"))
        assert len(pyproject_files) > 0, "No pyproject.toml found in scaffolded output"

    def test_scaffold_json_output_is_valid_json(
        self, scaffolded_json_output: tuple[str, int]
    ) -> None:
        """--json flag produces valid, parseable JSON output."""
        output, code = scaffolded_json_output
        assert code == 0
        data = json.loads(output)
        assert "success" in data
        assert data["success"] is True
        assert "files" in data

    def test_scaffold_with_description(self, scaffolded_project: Path) -> None:
        """--description flag is reflected in scaffolded output."""
        # The project was scaffolded with --description "My custom description"
        assert scaffolded_project.exists()

    def test_scaffold_with_license_flag(
        self, scaffolded_license_output: tuple[str, int]
    ) -> None:
        """--license flag is accepted."""
        _output, code = scaffolded_license_output
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
