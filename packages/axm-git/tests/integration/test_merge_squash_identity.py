"""Integration test: squash commit author resolved from a real profile config.

AXM-1826 AC1 over a real temp repo + a real git-profiles TOML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_git.core.runner import run_git
from axm_git.hooks.merge_squash import MergeSquashHook

pytestmark = pytest.mark.integration

_PROFILE_TOML = """\
[default]
name = "Squash Bot"
email = "squash@axm-protocol.io"
"""


def test_squash_commit_uses_resolved_profile(
    tmp_git_repo_with_branch: Path, tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC1: the squash commit author equals the resolved profile name/email."""
    config = tmp_path / "git-profiles.toml"
    config.write_text(_PROFILE_TOML)
    mocker.patch("axm_git.core.identity._DEFAULT_CONFIG_PATH", config)

    result = MergeSquashHook().execute(
        {
            "working_dir": str(tmp_git_repo_with_branch),
            "session_id": "abc",
            "protocol_name": "p",
        },
    )

    assert result.success is True
    log = run_git(["log", "-1", "--format=%an <%ae>"], tmp_git_repo_with_branch)
    assert log.stdout.strip() == "Squash Bot <squash@axm-protocol.io>"
