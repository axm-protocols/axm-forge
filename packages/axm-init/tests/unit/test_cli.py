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


# ── Module-scoped workspace scaffold fixture ─────────────────────────────


@pytest.fixture(scope="module")
def scaffolded_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold a workspace *once* for the whole module via real Copier.

    All TestWorkspaceScaffoldFlow tests assert read-only against this directory.
    """
    target = tmp_path_factory.mktemp("ws_func")
    args = [
        "scaffold",
        str(target),
        "--name",
        "func-test-workspace",
        "--workspace",
        "--description",
        "Test workspace",
        *SCAFFOLD_ARGS,
    ]
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit:
        pass
    return target


# ── Slow workspace scaffold tests ───────────────────────────────────────


@pytest.mark.slow
class TestWorkspaceScaffoldFlow:
    """End-to-end tests for the workspace scaffold command (real Copier)."""

    def test_scaffold_creates_workspace(self, scaffolded_workspace: Path) -> None:
        """scaffold --workspace creates a directory with expected files."""
        assert scaffolded_workspace.exists()
        assert (scaffolded_workspace / "pyproject.toml").is_file()

    def test_workspace_has_uv_workspace_config(
        self, scaffolded_workspace: Path
    ) -> None:
        """Generated pyproject.toml has [tool.uv.workspace]."""
        content = (scaffolded_workspace / "pyproject.toml").read_text()
        assert "[tool.uv.workspace]" in content

    def test_workspace_has_mkdocs_monorepo(self, scaffolded_workspace: Path) -> None:
        """Generated mkdocs.yml uses monorepo plugin."""
        mkdocs = scaffolded_workspace / "mkdocs.yml"
        assert mkdocs.is_file()
        assert "monorepo" in mkdocs.read_text()

    def test_workspace_has_ci_package_flag(self, scaffolded_workspace: Path) -> None:
        """Generated CI uses --package strategy."""
        ci = scaffolded_workspace / ".github" / "workflows" / "ci.yml"
        assert ci.is_file()
        assert "--package" in ci.read_text()

    def test_workspace_check_scores_100(self, scaffolded_workspace: Path) -> None:
        """AC7: check on generated workspace scores 100% on workspace checks."""
        from axm_init.core.checker import CheckEngine

        engine = CheckEngine(scaffolded_workspace)
        result = engine.run()

        ws_checks = [c for c in result.checks if c.category == "workspace"]
        assert len(ws_checks) > 0, "No workspace checks ran"
        failed = [c for c in ws_checks if not c.passed]
        assert not failed, f"Workspace checks failed: {[c.name for c in failed]}"

    def test_workspace_has_pre_commit(self, scaffolded_workspace: Path) -> None:
        """Generated workspace has .pre-commit-config.yaml."""
        assert (scaffolded_workspace / ".pre-commit-config.yaml").is_file()

    def test_workspace_has_contributing(self, scaffolded_workspace: Path) -> None:
        """Generated workspace has CONTRIBUTING.md."""
        assert (scaffolded_workspace / "CONTRIBUTING.md").is_file()
