"""Split from ``test_git_tag_tool.py`` — check_ci HEAD-correlation coverage."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.tag import check_ci


@pytest.mark.integration
class TestCheckCiHeadResolution:
    """Real-git HEAD resolution feeding check_ci correlation."""

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_tag_resolves_head_sha(
        self, _gh: MagicMock, mock_gh: MagicMock, tmp_path: Path
    ) -> None:
        """AC1: the headSha used for matching equals the repo's real HEAD.

        Real ``git rev-parse HEAD`` runs against a temp repo; only ``run_gh``
        (CI runs) is monkeypatched. The fake CI run carries the real HEAD sha,
        so the green verdict only holds if check_ci correlates against HEAD.
        """
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.io"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "t"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "f.txt").write_text("x")
        subprocess.run(
            ["git", "add", "."], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"],
            returncode=0,
            stdout=json.dumps(
                [{"conclusion": "success", "status": "completed", "headSha": head}]
            ),
            stderr="",
        )
        assert check_ci(tmp_path) == "green"
