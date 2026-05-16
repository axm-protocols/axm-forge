"""Split from ``test_register_member_in_workspace_root.py``."""

from pathlib import Path

from axm_init.adapters.workspace_patcher import patch_pyproject


class TestPyprojectGetsMemberDependency:
    """patch_pyproject adds the member as a workspace dependency."""

    def test_adds_dependency_and_source(self, workspace_root: Path) -> None:
        patch_pyproject(workspace_root, "my-lib")

        content = (workspace_root / "pyproject.toml").read_text()
        assert '"my-lib"' in content
        assert "[tool.uv.sources.my-lib]" in content
        assert "workspace = true" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_pyproject(workspace_root, "my-lib")
        content1 = (workspace_root / "pyproject.toml").read_text()
        patch_pyproject(workspace_root, "my-lib")
        content2 = (workspace_root / "pyproject.toml").read_text()
        assert content1 == content2


# ─ pyproject patching with sources marker ────────────────────────────────


def test_dep_already_in_sources_section_not_deps(tmp_path: Path) -> None:
    """Member name appears after sources marker → still adds to deps."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "ws"\nversion = "0.1.0"\n\n'
        'dependencies = [\n    "existing-pkg",\n]\n\n'
        "[tool.uv.sources]\n"
        "[tool.uv.sources.existing-pkg]\nworkspace = true\n"
    )
    patch_pyproject(tmp_path, "new-lib")
    content = pyproject.read_text()
    assert '"new-lib"' in content
    assert "[tool.uv.sources.new-lib]" in content
