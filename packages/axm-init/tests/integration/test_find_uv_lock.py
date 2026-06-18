from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.structure import check_uv_lock

WORKSPACE_PYPROJECT = """\
[tool.uv.workspace]
members = ["packages/*"]
"""

MEMBER_PYPROJECT = """\
[project]
name = "member-pkg"
version = "0.1.0"
"""


@pytest.mark.integration
@pytest.mark.parametrize(
    ("local_lock", "root_lock", "expected_passed", "expected_message"),
    [
        pytest.param(True, True, True, "uv.lock found", id="local-lock-preferred"),
        pytest.param(
            False,
            True,
            True,
            "uv.lock found (workspace root)",
            id="walks-to-workspace-root-lock",
        ),
        pytest.param(
            False, False, False, "uv.lock not found", id="none-when-no-lock-anywhere"
        ),
    ],
)
def test_uv_lock_resolution(
    tmp_path: Path,
    *,
    local_lock: bool,
    root_lock: bool,
    expected_passed: bool,
    expected_message: str,
) -> None:
    """AC1: check_uv_lock prefers a member-local uv.lock, walks to the
    workspace-root lock when the member has none, and fails when no lock exists
    anywhere — each path reports its own message."""
    member = tmp_path / "packages" / "member-pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(MEMBER_PYPROJECT)
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)
    if local_lock:
        (member / "uv.lock").write_text("version = 1\n")
    if root_lock:
        (tmp_path / "uv.lock").write_text("version = 1\n")

    result = check_uv_lock(member)

    assert result.passed is expected_passed
    assert result.message == expected_message
