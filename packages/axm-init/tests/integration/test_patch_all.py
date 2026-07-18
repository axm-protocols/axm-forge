"""patch_all orchestrates all per-file patches for a new workspace member."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters import workspace_patcher
from axm_init.adapters.workspace_patcher import patch_all


class TestPatchAllOrchestration:
    """patch_all applies every per-file patch and reports what changed."""

    def test_patches_all_files(self, workspace_root: Path) -> None:
        report = patch_all(workspace_root, "my-lib")
        assert len(report.patched) == 7
        assert "Makefile" in report.patched
        assert "mkdocs.yml" in report.patched
        assert "pyproject.toml" in report.patched
        assert "pyproject.toml (testpaths)" in report.patched
        assert ".github/dependabot.yml" in report.patched
        # release.yml is absent from the fixture → skipped, never patched.
        assert ".github/workflows/release.yml" in report.skipped
        assert ".github/workflows/release.yml" not in report.patched

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        """When no root files exist, nothing is patched; all are skipped."""
        report = patch_all(tmp_path, "my-lib")
        assert report.patched == []
        assert len(report.skipped) == 8
        assert report.failed == []

    def test_noop_patcher_not_reported_as_patched(self, tmp_path: Path) -> None:
        """AC1/AC2: a file whose patcher is a no-op is skipped, not patched."""
        (tmp_path / "Makefile").write_text("test-my-lib:\n\tuv run pytest\n")

        report = patch_all(tmp_path, "my-lib")

        assert "Makefile" not in report.patched
        assert "Makefile" in report.skipped

    def test_permission_error_surfaced_as_partial_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC3: a non-FileNotFoundError is caught and surfaced, not raised."""

        def _boom(root: Path, member_name: str) -> bool:
            raise PermissionError("denied")

        monkeypatch.setattr(workspace_patcher, "patch_makefile", _boom)

        report = patch_all(tmp_path, "my-lib")  # must not raise

        assert "Makefile" in report.failed
        assert report.has_partial_failure is True
        assert "Makefile" not in report.patched
        assert "Makefile" not in report.skipped
