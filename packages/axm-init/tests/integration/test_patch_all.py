"""patch_all orchestrates all per-file patches for a new workspace member."""

from __future__ import annotations

from pathlib import Path

from axm_init.adapters.workspace_patcher import patch_all


class TestPatchAllOrchestration:
    """patch_all applies every per-file patch and reports what changed."""

    def test_patches_all_files(self, workspace_root: Path) -> None:
        patched = patch_all(workspace_root, "my-lib")
        assert len(patched) == 6
        assert "Makefile" in patched
        assert "mkdocs.yml" in patched
        assert "pyproject.toml" in patched
        assert "pyproject.toml (testpaths)" in patched

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        """When no root files exist, patch_all returns empty list."""
        patched = patch_all(tmp_path, "my-lib")
        assert patched == []
