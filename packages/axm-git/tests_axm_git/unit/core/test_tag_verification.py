"""Read-only release tag verification contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_git.core.tag_verification import (
    VerifiedTag,
    release_version,
    verify_remote_tag,
    verify_tag,
)

COMMIT = "a" * 40
TAG_OBJECT = "b" * 40


def _result(stdout: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["git"], code, stdout, "git failure" if code else ""
    )


@patch("axm_git.core.tag_verification.run_git")
def test_verify_tag_reads_version_and_commit(mock_git: MagicMock) -> None:
    mock_git.side_effect = [_result(TAG_OBJECT), _result(COMMIT)]
    result = verify_tag(Path("/repo"), "pkg/v1.2.3", "pkg/", COMMIT)
    assert result == VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)


@pytest.mark.parametrize(
    ("name", "prefix", "expected"),
    [("v1.2.3", "", "1.2.3"), ("ast/v0.4.0", "ast/", "0.4.0")],
)
def test_release_version_reads_prefixed_semver(
    name: str, prefix: str, expected: str
) -> None:
    assert release_version(name, prefix) == expected


@pytest.mark.parametrize(
    ("name", "prefix", "message"),
    [
        ("other/v1.2.3", "pkg/", "prefix"),
        ("pkg/1.2.3", "pkg/", "prefix"),
        ("ast/v0.4.0", "", "prefix"),
        ("pkg/vbanana", "pkg/", "semver"),
        ("pkg/v1.2.3-rc1", "pkg/", "semver"),
    ],
)
@patch("axm_git.core.tag_verification.run_git")
def test_invalid_version_is_rejected_before_git(
    mock_git: MagicMock, name: str, prefix: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        verify_tag(Path("/repo"), name, prefix, COMMIT)
    mock_git.assert_not_called()


@pytest.mark.parametrize(
    ("output", "code", "message"),
    [("", 1, "Cannot resolve"), ("", 0, "Cannot resolve"), ("c" * 40, 0, "targets")],
)
@patch("axm_git.core.tag_verification.run_git")
def test_unverified_tag_cannot_pass(
    mock_git: MagicMock, output: str, code: int, message: str
) -> None:
    mock_git.return_value = _result(output, code)
    with pytest.raises(ValueError, match=message):
        verify_tag(Path("/repo"), "v1.2.3", "", COMMIT)


@patch("axm_git.core.tag_verification.run_git")
def test_remote_requires_annotated_object_and_commit(mock_git: MagicMock) -> None:
    mock_git.return_value = _result(
        f"{TAG_OBJECT}\trefs/tags/pkg/v1.2.3\n{COMMIT}\trefs/tags/pkg/v1.2.3^{{}}\n"
    )
    assert (
        verify_remote_tag(
            Path("/repo"), "pkg/v1.2.3", VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)
        )
        is None
    )


@pytest.mark.parametrize(
    "output",
    [
        "",
        "malformed",
        f"{COMMIT}\trefs/tags/pkg/v1.2.3",
        f"{TAG_OBJECT}\trefs/tags/pkg/v1.2.3\nwrong\trefs/tags/pkg/v1.2.3^{{}}",
        f"wrong\trefs/tags/pkg/v1.2.3\n{COMMIT}\trefs/tags/pkg/v1.2.3^{{}}",
    ],
)
@patch("axm_git.core.tag_verification.run_git")
def test_remote_mismatch_is_not_success(mock_git: MagicMock, output: str) -> None:
    mock_git.return_value = _result(output)
    error = verify_remote_tag(
        Path("/repo"), "pkg/v1.2.3", VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)
    )
    assert error and "does not match" in error


@pytest.mark.parametrize(
    ("output", "code", "reason"),
    [
        pytest.param("", 2, "does not advertise", id="absent"),
        pytest.param(f"{COMMIT}\trefs/tags/v1.2.3", 0, "lightweight", id="lightweight"),
        pytest.param(
            f"{'c' * 40}\trefs/tags/v1.2.3\n{COMMIT}\trefs/tags/v1.2.3^{{}}",
            0,
            "tag object",
            id="other_object",
        ),
        pytest.param(
            f"{TAG_OBJECT}\trefs/tags/v1.2.3\n{'c' * 40}\trefs/tags/v1.2.3^{{}}",
            0,
            "peels to",
            id="other_commit",
        ),
    ],
)
@patch("axm_git.core.tag_verification.run_git")
def test_remote_mismatch_names_the_difference(
    mock_git: MagicMock, output: str, code: int, reason: str
) -> None:
    mock_git.return_value = _result(output, code)
    error = verify_remote_tag(
        Path("/repo"), "v1.2.3", VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)
    )
    assert error and reason in error


@pytest.mark.parametrize("timeout", [False, True])
@patch("axm_git.core.tag_verification.run_git")
def test_remote_unavailable_reports_failure(mock_git: MagicMock, timeout: bool) -> None:
    if timeout:
        mock_git.side_effect = subprocess.TimeoutExpired(["git", "ls-remote"], 30)
    else:
        mock_git.return_value = _result(code=128)
    error = verify_remote_tag(
        Path("/repo"), "v1.2.3", VerifiedTag("1.2.3", COMMIT, TAG_OBJECT)
    )
    assert error and ("timed out" if timeout else "Cannot verify") in error
