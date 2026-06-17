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
def test_local_lock_preferred(tmp_path: Path) -> None:
    """AC1: a member with its own uv.lock resolves to that local lock."""
    member = tmp_path / "packages" / "member-pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(MEMBER_PYPROJECT)
    (member / "uv.lock").write_text("version = 1\n")
    # workspace root also has a lock — local must win
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)
    (tmp_path / "uv.lock").write_text("version = 1\n")

    result = check_uv_lock(member)

    assert result.passed is True
    assert result.message == "uv.lock found"


@pytest.mark.integration
def test_walks_to_workspace_root_lock(tmp_path: Path) -> None:
    """AC1: a member without a local lock resolves to the workspace-root lock."""
    member = tmp_path / "packages" / "member-pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(MEMBER_PYPROJECT)
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)
    (tmp_path / "uv.lock").write_text("version = 1\n")

    result = check_uv_lock(member)

    assert result.passed is True
    assert result.message == "uv.lock found (workspace root)"


@pytest.mark.integration
def test_none_when_no_lock_anywhere(tmp_path: Path) -> None:
    """AC1: a workspace with no uv.lock anywhere fails the check."""
    member = tmp_path / "packages" / "member-pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(MEMBER_PYPROJECT)
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)

    result = check_uv_lock(member)

    assert result.passed is False
    assert result.message == "uv.lock not found"
