"""Split from ``test_register_member_in_workspace_root.py``."""

from pathlib import Path

from axm_init.adapters.workspace_patcher import patch_mkdocs


class TestMkdocsGetsMemberInclude:
    """patch_mkdocs adds nav include for the new member's docs."""

    def test_adds_include(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")

        content = (workspace_root / "mkdocs.yml").read_text()
        assert "!include ./packages/my-lib/mkdocs.yml" in content
        assert "my-lib:" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")
        content1 = (workspace_root / "mkdocs.yml").read_text()
        patch_mkdocs(workspace_root, "my-lib")
        content2 = (workspace_root / "mkdocs.yml").read_text()
        assert content1 == content2
