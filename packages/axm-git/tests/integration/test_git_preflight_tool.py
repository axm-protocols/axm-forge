"""Split from ``test_flows.py``."""

import subprocess
from pathlib import Path

from axm_git.tools.commit_preflight import GitPreflightTool


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


class TestPreflightFlow:
    """Functional tests for git_preflight."""

    def test_preflight_shows_changes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        # Modify a file
        (tmp_path / "README.md").write_text("# Modified\n")
        # Add a new file
        (tmp_path / "new.py").write_text("print('hello')\n")

        result = GitPreflightTool().execute(path=str(tmp_path))
        assert result.success
        assert not result.data["clean"]
        paths = [f["path"] for f in result.data["files"]]
        assert "README.md" in paths
