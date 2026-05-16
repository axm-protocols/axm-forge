"""Split from ``test_flows.py``."""

import subprocess
from pathlib import Path

from axm_git.tools.branch import GitBranchTool


def _init_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    # Initial commit
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: init", "--no-verify"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


class TestBranchFlow:
    """Functional tests for git_branch."""

    def test_create_and_checkout(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        result = GitBranchTool().execute(name="feat/new", path=str(tmp_path))
        assert result.success
        assert result.data["branch"] == "feat/new"

        # Verify the branch exists in git branch output.
        branches = subprocess.run(
            ["git", "branch"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat/new" in branches.stdout

        # Verify HEAD is on the new branch.
        head = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert head.stdout.strip() == "feat/new"

    def test_checkout_existing(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)

        # Create a branch manually first.
        subprocess.run(
            ["git", "checkout", "-b", "feat/existing"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )
        # Go back to main/master.
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        # Use checkout_only to switch to the existing branch.
        result = GitBranchTool().execute(
            name="feat/existing", checkout_only=True, path=str(tmp_path)
        )
        assert result.success
        assert result.data["branch"] == "feat/existing"
