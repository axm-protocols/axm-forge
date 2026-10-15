"""Bounded timeout evidence retains retry causality without aliasing."""

import subprocess

import pytest

from axm_git.core.commit_timeout import CommitTimeoutError


@pytest.mark.parametrize("output", [None, b"invalid-utf8:\xff", "x" * 20000])
def test_timeout_evidence_is_bounded_and_snapshotted(
    output: str | bytes | None,
) -> None:
    """Missing, binary and large output stay safe while metadata is copied."""
    fixed = ["a.txt"]
    error = CommitTimeoutError(
        subprocess.TimeoutExpired(
            ["git", "commit"], 30, output=output, stderr=b"stderr"
        ),
        retried=True,
        auto_fixed=fixed,
    )
    fixed.append("foreign.txt")
    assert isinstance(error, subprocess.TimeoutExpired)
    assert error.auto_fixed == ["a.txt"]
    assert error.retried
    assert error.seconds == 30
    assert "stderr" in error.output
    assert len(error.output) <= 8192 + 1 + len("stderr")
    assert str(error) == "git timed out after 30s"
