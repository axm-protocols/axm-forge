"""Registering a new member patches CI workflows (build matrix + publish tags)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.workspace_patcher import patch_ci, patch_publish


class TestCiMatrixGetsMember:
    """patch_ci adds the new member to the CI build matrix."""

    def test_adds_package_to_matrix(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert "- my-lib" in content
        assert "- existing-pkg" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")
        content1 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        patch_ci(workspace_root, "my-lib")
        content2 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert content1 == content2

    def test_missing_ci_workflow_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_ci(tmp_path, "my-lib")


class TestPublishWorkflowGetsMemberTag:
    """patch_publish adds member-prefixed tag pattern."""

    def test_adds_tag_pattern(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "publish.yml").read_text()
        assert "my-lib/v*" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")
        content1 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        patch_publish(workspace_root, "my-lib")
        content2 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        assert content1 == content2

    def test_missing_publish_workflow_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_publish(tmp_path, "my-lib")

    def test_adds_tags_section_when_absent(self, tmp_path: Path) -> None:
        """patch_publish adds tags section if missing from existing publish.yml."""
        publish_file = tmp_path / ".github" / "workflows" / "publish.yml"
        publish_file.parent.mkdir(parents=True, exist_ok=True)
        publish_file.write_text("name: Publish\n\njobs:\n  build:\n")

        patch_publish(tmp_path, "my-lib")

        content = publish_file.read_text()
        assert "tags:" in content
        assert "my-lib/v*" in content
