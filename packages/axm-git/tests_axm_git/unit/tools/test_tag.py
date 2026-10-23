"""Unit tests for axm_git.tools.tag (no real I/O)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_git.core.tag_verification import VerifiedTag
from axm_git.tools.tag import (
    GitTagTool,
    check_ci,
    resolve_version,
)


def _mock_completed(
    stdout: str = "",
    stderr: str = "",
    rc: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Create a mock CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
    )


class TestResolveVersionOverride:
    """Override-validation behavior of resolve_version (pure, no I/O)."""

    def test_resolve_version_rejects_invalid_override(self) -> None:
        """AC3: a non-semver override is rejected (no vbanana tag)."""
        with pytest.raises(ValueError):
            resolve_version("banana", "v1.0.0", [])

    def test_resolve_version_rejects_non_increasing_override(self) -> None:
        """AC4: an override equal to the current tag is rejected."""
        with pytest.raises(ValueError):
            resolve_version("v1.0.0", "v1.0.0", [])

    def test_resolve_version_accepts_greater_override(self) -> None:
        """AC4: a strictly-greater override is accepted."""
        assert resolve_version("v2.0.0", "v1.0.0", []) == (
            "v2.0.0",
            "override",
            False,
        )


COMMIT = "a" * 40
TAG_OBJECT = "b" * 40
VERIFIED = VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)


@pytest.fixture
def tagging(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Stub everything up to tag creation; publication seams stay patchable."""
    mocker.patch("axm_git.tools.tag.get_tag_prefix", return_value="")
    mocker.patch(
        "axm_git.tools.tag._preflight",
        return_value=("green", None, ["feat: initial"]),
    )
    mocker.patch("axm_git.tools.tag._head_sha", return_value=COMMIT)
    return {
        "run_git": mocker.patch(
            "axm_git.tools.tag.run_git", return_value=_mock_completed()
        ),
        "verify_tag": mocker.patch(
            "axm_git.tools.tag.verify_tag", return_value=VERIFIED
        ),
        "verify_remote_tag": mocker.patch(
            "axm_git.tools.tag.verify_remote_tag", return_value=None
        ),
    }


def _git_verbs(run_git: MagicMock) -> list[str]:
    return [call.args[0][0] for call in run_git.call_args_list]


class TestGitTagPublication:
    """Post-creation paths: every result carries pushed and remote_verified."""

    def test_success_reports_git_evidence(self, tagging: dict[str, MagicMock]) -> None:
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert result.success, result.error
        assert result.data["resolved_version"] == "1.2.3"
        assert result.data["version_source"] == "git_tag"
        assert result.data["tag_commit"] == COMMIT
        assert result.data["tag_object"] == TAG_OBJECT
        assert result.data["pushed"] is True
        assert result.data["remote_verified"] is True
        tag_call, push_call = tagging["run_git"].call_args_list
        assert tag_call.args[0] == ["tag", "-a", "v1.2.3", COMMIT, "-m", "v1.2.3"]
        assert push_call.args[0] == ["push", "origin", f"{TAG_OBJECT}:refs/tags/v1.2.3"]
        assert "remote verified" in (result.text or "")

    def test_remote_verification_failure_preserves_push_receipt(
        self, tagging: dict[str, MagicMock]
    ) -> None:
        """A successful push with unverified remote state must not report success."""
        tagging["verify_remote_tag"].return_value = "remote tag differs"
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert not result.success
        assert result.error == "remote tag differs"
        assert result.data["pushed"] is True
        assert result.data["remote_verified"] is False
        assert result.data["full_tag"] == "v1.2.3"
        assert result.data["tag_object"] == TAG_OBJECT
        assert "pushed · remote unverified" in (result.text or "")

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(ValueError("Tag v1.2.3 targets c, expected a"), id="moved"),
            pytest.param(
                subprocess.TimeoutExpired(["git", "rev-parse"], 30), id="timeout"
            ),
        ],
    )
    def test_unverified_local_tag_is_kept_and_not_pushed(
        self, tagging: dict[str, MagicMock], exc: Exception
    ) -> None:
        tagging["verify_tag"].side_effect = exc
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert not result.success
        assert "created locally but failed verification" in (result.error or "")
        assert result.data["full_tag"] == "v1.2.3"
        assert result.data["pushed"] is False
        assert result.data["remote_verified"] is False
        assert result.data["resolved_version"] is None
        assert _git_verbs(tagging["run_git"]) == ["tag"]
        tagging["verify_remote_tag"].assert_not_called()
        assert "v1.2.3 kept locally · not pushed" in (result.text or "")

    def test_rejected_push_skips_remote_verification(
        self, tagging: dict[str, MagicMock]
    ) -> None:
        tagging["run_git"].side_effect = [
            _mock_completed(),
            _mock_completed(stderr="! [rejected] (already exists)", rc=1),
        ]
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert not result.success
        assert "push to origin failed: ! [rejected]" in (result.error or "")
        assert result.data["pushed"] is False
        assert result.data["remote_verified"] is False
        tagging["verify_remote_tag"].assert_not_called()

    @pytest.mark.parametrize(
        ("remote_error", "success"),
        [
            pytest.param(None, True, id="origin_confirms"),
            pytest.param("origin unreachable", False, id="origin_unconfirmed"),
        ],
    )
    def test_push_timeout_is_settled_by_origin(
        self,
        tagging: dict[str, MagicMock],
        remote_error: str | None,
        success: bool,
    ) -> None:
        """A timed-out push only counts as pushed when origin advertises the tag."""
        tagging["run_git"].side_effect = [
            _mock_completed(),
            subprocess.TimeoutExpired(["git", "push"], 30),
        ]
        tagging["verify_remote_tag"].return_value = remote_error
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert result.success is success
        assert result.data["pushed"] is success
        assert result.data["remote_verified"] is success
        if not success:
            assert "git push timed out after 30s" in (result.error or "")
            assert "origin unreachable" in (result.error or "")

    @pytest.mark.parametrize("version", ["1.2", "v1.2.3-rc1", "ast/v1.2.3"])
    def test_invalid_version_creates_no_tag(
        self, tagging: dict[str, MagicMock], version: str
    ) -> None:
        result = GitTagTool().execute(path="/repo", version=version)
        assert not result.success
        assert "Invalid semver" in (result.error or "")
        tagging["run_git"].assert_not_called()

    def test_unresolvable_head_creates_no_tag(
        self, tagging: dict[str, MagicMock], mocker: MockerFixture
    ) -> None:
        mocker.patch("axm_git.tools.tag._head_sha", return_value=None)
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert not result.success
        assert result.error == "Cannot resolve HEAD before tagging"
        tagging["run_git"].assert_not_called()

    def test_tag_creation_timeout_reports_command(
        self, tagging: dict[str, MagicMock]
    ) -> None:
        tagging["run_git"].side_effect = subprocess.TimeoutExpired(["git", "tag"], 30)
        result = GitTagTool().execute(path="/repo", version="1.2.3")
        assert not result.success
        assert result.error == "git timed out after 30s"
        tagging["verify_tag"].assert_not_called()


class TestGitTagToolUnit:
    """Unit-scope tests for GitTagTool (mocked I/O only)."""

    def test_name(self) -> None:
        tool = GitTagTool()
        assert tool.name == "git_tag"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_dirty_tree(self, _gh: MagicMock, mock_git: MagicMock) -> None:
        mock_git.return_value = _mock_completed("M src/foo.py")
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "Uncommitted" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_no_commits(self, _gh: MagicMock, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag":
                return _mock_completed("v0.7.0\nv0.6.0")
            if args[0] == "log":
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "No commits" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.check_ci", return_value="red")
    def test_ci_red_blocks(self, _ci: MagicMock, mock_git: MagicMock) -> None:
        """CI red prevents tagging."""
        mock_git.return_value = _mock_completed("")  # clean status
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "CI is red" in (result.error or "")


_HEAD = "abc123"


def _head_proc() -> subprocess.CompletedProcess[str]:
    """Fake ``git rev-parse HEAD`` returning the canonical test HEAD sha."""
    return _mock_completed(stdout=_HEAD + "\n")


class TestCheckCi:
    """Test the check_ci helper."""

    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_skipped_when_gh_unavailable(self, _gh: MagicMock) -> None:
        assert check_ci(Path("/tmp")) == "skipped"

    @pytest.mark.parametrize(
        ("returncode", "stdout", "expected_status"),
        [
            pytest.param(
                0,
                json.dumps(
                    [{"conclusion": "success", "status": "completed", "headSha": _HEAD}]
                ),
                "green",
                id="green",
            ),
            pytest.param(
                0,
                json.dumps(
                    [{"conclusion": None, "status": "in_progress", "headSha": _HEAD}]
                ),
                "pending",
                id="pending",
            ),
            pytest.param(
                0,
                json.dumps(
                    [{"conclusion": "failure", "status": "completed", "headSha": _HEAD}]
                ),
                "red",
                id="red",
            ),
            pytest.param(0, "[]", "skipped", id="empty_runs"),
            pytest.param(1, "", "skipped", id="gh_returncode_nonzero"),
        ],
    )
    @patch("axm_git.tools.tag.run_git", return_value=_head_proc())
    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_check_ci_from_gh_output(
        self,
        _gh: MagicMock,
        mock_gh: MagicMock,
        _git: MagicMock,
        returncode: int,
        stdout: str,
        expected_status: str,
    ) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=returncode, stdout=stdout, stderr=""
        )
        assert check_ci(Path("/tmp")) == expected_status

    @patch("axm_git.tools.tag.run_gh", side_effect=FileNotFoundError)
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_exception_returns_error(self, _gh: MagicMock, _mock_gh: MagicMock) -> None:
        assert check_ci(Path("/tmp")) == "error"

    @patch("axm_git.tools.tag.run_git", return_value=_head_proc())
    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_ci_green_only_when_headsha_matches(
        self, _gh: MagicMock, mock_gh: MagicMock, _git: MagicMock
    ) -> None:
        """AC1: green is reported from the run whose headSha equals HEAD."""
        mock_gh.return_value = _mock_completed(
            stdout=json.dumps(
                [{"conclusion": "success", "status": "completed", "headSha": _HEAD}]
            )
        )
        assert check_ci(Path("/tmp")) == "green"

    @patch(
        "axm_git.tools.tag.run_git",
        return_value=_mock_completed(stdout="def456\n"),
    )
    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_ci_stale_green_not_reported(
        self, _gh: MagicMock, mock_gh: MagicMock, _git: MagicMock
    ) -> None:
        """AC3: a green run on an older SHA does not yield green once HEAD moved."""
        mock_gh.return_value = _mock_completed(
            stdout=json.dumps(
                [{"conclusion": "success", "status": "completed", "headSha": "abc123"}]
            )
        )
        assert check_ci(Path("/tmp")) != "green"

    @patch(
        "axm_git.tools.tag.run_git",
        return_value=_mock_completed(stdout="def456\n"),
    )
    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_ci_no_run_for_head_is_pending(
        self, _gh: MagicMock, mock_gh: MagicMock, _git: MagicMock
    ) -> None:
        """AC2: when no run matches HEAD, return non-green (pending)."""
        mock_gh.return_value = _mock_completed(
            stdout=json.dumps(
                [{"conclusion": "success", "status": "completed", "headSha": "abc123"}]
            )
        )
        result = check_ci(Path("/tmp"))
        assert result != "green"
        assert result == "pending"

    @patch("axm_git.tools.tag.run_git", return_value=_head_proc())
    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_ci_unrelated_red_does_not_block(
        self, _gh: MagicMock, mock_gh: MagicMock, _git: MagicMock
    ) -> None:
        """AC4: a red run on an unrelated SHA is ignored in favor of HEAD's green."""
        mock_gh.return_value = _mock_completed(
            stdout=json.dumps(
                [
                    {
                        "conclusion": "failure",
                        "status": "completed",
                        "headSha": "zzz999",
                    },
                    {"conclusion": "success", "status": "completed", "headSha": _HEAD},
                ]
            )
        )
        assert check_ci(Path("/tmp")) == "green"
