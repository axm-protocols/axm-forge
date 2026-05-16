"""Registering a new member patches root Makefile, mkdocs, pyproject, testpaths."""

from __future__ import annotations

from pathlib import Path

from axm_init.adapters.workspace_patcher import (
    patch_testpaths,
)


class TestTestpathsGetsMemberEntry:
    """patch_testpaths registers the member's tests directory."""

    def test_adds_testpath(self, workspace_root: Path) -> None:
        patch_testpaths(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert "packages/my-lib/tests" in content
        assert "[tool.pytest.ini_options]" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_testpaths(workspace_root, "my-lib")
        content1 = (workspace_root / "pyproject.toml").read_text()
        patch_testpaths(workspace_root, "my-lib")
        content2 = (workspace_root / "pyproject.toml").read_text()
        assert content1 == content2

    def test_creates_section_if_absent(self, workspace_root: Path) -> None:
        content = (workspace_root / "pyproject.toml").read_text()
        assert "[tool.pytest.ini_options]" not in content

        patch_testpaths(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert "[tool.pytest.ini_options]" in content
        assert "packages/my-lib/tests" in content

    def test_adds_to_existing_testpaths(self, workspace_root: Path) -> None:
        pyproject = workspace_root / "pyproject.toml"
        content = pyproject.read_text()
        content += (
            "\n[tool.pytest.ini_options]\n"
            'testpaths = [\n    "packages/existing/tests",\n]\n'
        )
        pyproject.write_text(content)

        patch_testpaths(workspace_root, "my-lib")

        result = pyproject.read_text()
        assert "packages/existing/tests" in result
        assert "packages/my-lib/tests" in result


# ─ TOML array edge cases (covered via public patch_testpaths) ──────────────────


def test_section_exists_key_missing(tmp_path: Path) -> None:
    """Section exists without testpaths key → key is added with array."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "ws"\n\n'
        '[tool.pytest.ini_options]\nimport_mode = "importlib"\n'
    )
    patch_testpaths(tmp_path, "new-pkg")
    result = pyproject.read_text()
    assert '"packages/new-pkg/tests"' in result
    assert "[tool.pytest.ini_options]" in result
    assert 'import_mode = "importlib"' in result


def test_single_line_array(tmp_path: Path) -> None:
    """Existing single-line testpaths array → entry appended in-place."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "ws"\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = [\n    "packages/a/tests"\n]\n'
    )
    patch_testpaths(tmp_path, "b")
    result = pyproject.read_text()
    assert '"packages/a/tests"' in result
    assert '"packages/b/tests"' in result
