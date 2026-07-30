"""Split from ``test_register_member_in_workspace_root.py``."""

from pathlib import Path

import pytest

from axm_init.adapters.workspace_patcher import patch_makefile


class TestMakefileGetsMemberTargets:
    """patch_makefile adds per-member test/lint targets."""

    def test_adds_targets(self, workspace_root: Path) -> None:
        patch_makefile(workspace_root, "my-lib")

        content = (workspace_root / "Makefile").read_text()
        assert "test-my-lib:" in content
        assert "lint-my-lib:" in content
        assert "--package my-lib" in content
        assert "packages/my-lib/src/my_lib/" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_makefile(workspace_root, "my-lib")
        content1 = (workspace_root / "Makefile").read_text()
        patch_makefile(workspace_root, "my-lib")
        content2 = (workspace_root / "Makefile").read_text()
        assert content1 == content2

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_makefile(tmp_path, "my-lib")

    def test_prefix_collision_does_not_skip(self, tmp_path: Path) -> None:
        """A member whose target is a prefix of an existing one is still added.

        Regression: ``"test-foo" in content`` (substring) skipped ``foo`` when
        a ``test-foo-bar:`` target already existed. The anchored guard must
        create ``test-foo``/``lint-foo`` regardless.
        """
        makefile = tmp_path / "Makefile"
        makefile.write_text("test-foo-bar:\n\tuv run pytest --package foo-bar -q\n")
        patch_makefile(tmp_path, "foo")
        content = makefile.read_text()
        assert "test-foo:" in content
        assert "lint-foo:" in content
        assert "test-foo-bar:" in content
