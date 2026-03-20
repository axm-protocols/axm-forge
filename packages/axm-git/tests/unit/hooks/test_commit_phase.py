"""Tests for CommitPhaseHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import run_git
from axm_git.hooks.commit_phase import CommitPhaseHook


class TestCommitPhaseHook:
    """Tests for CommitPhaseHook (legacy mode)."""

    def test_commits_changes(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "file.txt").write_text("hello")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["message"] == "[axm] plan"
        assert result.metadata["commit"]  # short hash is non-empty

    def test_nothing_to_commit(self, tmp_git_repo: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_custom_message_format(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "f.txt").write_text("x")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            message_format="[AXM:{phase}]",
        )
        assert result.success
        assert result.metadata["message"] == "[AXM:plan]"

    def test_not_git_repo(self, tmp_path: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_path), "phase_name": "p"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            enabled=False,
        )
        assert result.success
        assert result.metadata.get("skipped") is True
        assert result.metadata.get("reason") == "git disabled"

    def test_legacy_mode_unchanged(self, tmp_git_repo: Path) -> None:
        """Legacy mode still works: stages all, commits with [axm] {phase}."""
        (tmp_git_repo / "a.txt").write_text("a")
        (tmp_git_repo / "b.txt").write_text("b")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "close"},
        )
        assert result.success
        assert result.metadata["message"] == "[axm] close"
        # Both files should be committed
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "a.txt" in committed
        assert "b.txt" in committed


class TestCommitFromOutputs:
    """Tests for CommitPhaseHook from_outputs mode."""

    def test_stages_specific_files(self, tmp_git_repo: Path) -> None:
        """Only listed files are committed, not others."""
        (tmp_git_repo / "included.txt").write_text("yes")
        (tmp_git_repo / "excluded.txt").write_text("no")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat(test): add included",
                        "files": ["included.txt"],
                    },
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "feat(test): add included"

        # Only included.txt should be in the commit
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "included.txt" in committed
        assert "excluded.txt" not in committed

    def test_message_and_body(self, tmp_git_repo: Path) -> None:
        """Commit has both message and body."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat(runner): extract",
                        "body": "Closes: AXM-605",
                        "files": ["f.txt"],
                    },
                },
            },
            from_outputs=True,
        )

        assert result.success
        # Verify full commit message
        log = run_git(["log", "-1", "--format=%B"], tmp_git_repo)
        full_msg = log.stdout.strip()
        assert "feat(runner): extract" in full_msg
        assert "Closes: AXM-605" in full_msg

    def test_returns_hash(self, tmp_git_repo: Path) -> None:
        """Result contains commit hash and message."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat: test hash",
                        "files": ["f.txt"],
                    },
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert len(result.metadata["commit"]) >= 7  # short hash
        assert result.metadata["message"] == "feat: test hash"

    def test_missing_commit_spec_fails(self, tmp_git_repo: Path) -> None:
        """Fails with clear message when commit_spec is absent."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "outputs": {}},
            from_outputs=True,
        )

        assert not result.success
        assert "commit_spec" in (result.error or "")

    def test_missing_outputs_fails(self, tmp_git_repo: Path) -> None:
        """Fails when outputs key is missing entirely."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
            from_outputs=True,
        )

        assert not result.success
        assert "commit_spec" in (result.error or "")

    def test_missing_files_key_fails(self, tmp_git_repo: Path) -> None:
        """Fails when commit_spec has no files key."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {"message": "feat: no files"},
                },
            },
            from_outputs=True,
        )

        assert not result.success
        assert "'files'" in (result.error or "")

    def test_nonexistent_file_fails(self, tmp_git_repo: Path) -> None:
        """Fails when a listed file does not exist."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat: ghost",
                        "files": ["deleted.py"],
                    },
                },
            },
            from_outputs=True,
        )

        assert not result.success
        assert "deleted.py" in (result.error or "")

    def test_nothing_to_commit(self, tmp_git_repo: Path) -> None:
        """Skips when all listed files are already clean."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat: clean",
                        "files": [".gitkeep"],
                    },
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "nothing to commit"

    def test_body_absent_ok(self, tmp_git_repo: Path) -> None:
        """Commit works without body — message only, no error."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "outputs": {
                    "commit_spec": {
                        "message": "feat: no body",
                        "files": ["f.txt"],
                    },
                },
            },
            from_outputs=True,
        )

        assert result.success
        log = run_git(["log", "-1", "--format=%B"], tmp_git_repo)
        assert log.stdout.strip() == "feat: no body"


class TestCommitPhaseWorkspace:
    """Tests for CommitPhaseHook in workspace (nested package) layouts."""

    def test_workspace_package_commits(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """CommitPhaseHook finds git root and commits from a nested package."""
        _, pkg_dir = tmp_workspace_repo

        (pkg_dir / "src" / "hello.py").write_text("# changed\n")

        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir), "phase_name": "close"},
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "[axm] close"

    def test_workspace_nothing_to_commit(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Skips when package dir is clean (even if workspace root has changes)."""
        git_root, pkg_dir = tmp_workspace_repo

        # Only change at workspace root — package is clean
        (git_root / "noise.txt").write_text("workspace noise")
        run_git(["add", "noise.txt"], git_root)
        run_git(["commit", "-m", "noise"], git_root)

        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir), "phase_name": "close"},
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "nothing to commit"
