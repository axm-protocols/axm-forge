"""Integration: a fresh uv-workspace scaffold generates functional CI & completes.

Covers AXM-2047 (F3/F4/F8): the scaffolded ``publish.yml`` must build publishable
members (not a no-op root ``uv build``), the scaffolded ``ci.yml`` must use a
well-formed pytest invocation (``uv run --package <pkg> pytest ...`` with the
flag *before* ``pytest``), and rendering a fresh member-less workspace must NOT
fail/rollback on the post-copy ``uv sync`` task.

Rendering goes through Copier's ``run_copy`` (the same engine the scaffold tool
drives). AC1/AC2 render files only (``skip_tasks=True``) and assert on content.
AC3 runs the full post-copy ``_tasks`` (``skip_tasks=False``) to prove the fresh
scaffold completes without rollback now that ``uv sync`` is gated on member
presence; it is skipped when ``git``/``uv`` are unavailable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from copier import run_copy

from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

_DATA = {
    "workspace_name": "fresh-ws",
    "description": "Test workspace",
    "org": "test-org",
    "author_name": "Test Author",
    "author_email": "test@test.com",
    "license": "Apache-2.0",
    "license_holder": "test-org",
}


def _render(destination: Path, *, skip_tasks: bool) -> None:
    """Render the uv-workspace template into *destination* via real Copier."""
    run_copy(
        src_path=str(get_template_path(TemplateType.WORKSPACE)),
        dst_path=str(destination),
        data=dict(_DATA),
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=skip_tasks,
    )


@pytest.fixture(scope="module")
def rendered_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the workspace once (files only, no post-copy tasks)."""
    target = tmp_path_factory.mktemp("fresh_ws")
    _render(target, skip_tasks=True)
    return target


def test_workspace_publish_builds_members(rendered_workspace: Path) -> None:
    """AC1: publish.yml builds publishable members, not a no-op root ``uv build``."""
    publish = (rendered_workspace / ".github" / "workflows" / "publish.yml").read_text()
    # The build step must target members, not bare root ``uv build``.
    assert "--package" in publish or "packages/" in publish, publish
    lines = [ln.strip() for ln in publish.splitlines()]
    assert "- run: uv build" not in lines, "root `uv build` builds no member"


def test_workspace_ci_pytest_invocation_valid(rendered_workspace: Path) -> None:
    """AC2: ci.yml uses ``uv run --package <pkg> pytest`` (flag before pytest)."""
    ci = (rendered_workspace / ".github" / "workflows" / "ci.yml").read_text()
    # ``--package`` is a ``uv run`` flag and must precede ``pytest``, never be
    # passed *to* pytest (``uv run pytest --package`` fails).
    assert "uv run pytest --package" not in ci, ci
    assert "--package" in ci
    pkg_line = next(
        ln for ln in ci.splitlines() if "pytest" in ln and "--package" in ln
    )
    assert pkg_line.index("--package") < pkg_line.index("pytest"), pkg_line


def test_workspace_ci_matrix_is_documented_placeholder(
    rendered_workspace: Path,
) -> None:
    """AC2: the package matrix is an obvious documented placeholder, not silent."""
    ci = (rendered_workspace / ".github" / "workflows" / "ci.yml").read_text()
    assert "placeholder" in ci.lower()
    # A comment must flag it so the user knows to fill it in.
    assert any("#" in ln and "placeholder" in ln.lower() for ln in ci.splitlines()), (
        "placeholder matrix must be documented with a comment"
    )


@pytest.mark.slow
@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("uv") is None,
    reason="git and uv required to run post-copy _tasks",
)
def test_fresh_workspace_scaffold_no_rollback(tmp_path: Path) -> None:
    """AC3: a fresh member-less scaffold completes (gated uv sync) without rollback."""
    target = tmp_path / "ws"
    # skip_tasks=False runs the real post-copy _tasks; the gated ``uv sync``
    # must be skipped on a member-less workspace, so this must not raise/rollback.
    _render(target, skip_tasks=False)
    # No rollback: the rendered tree survives and core files are present.
    # (A fresh member-less workspace has no ``packages/`` dir yet — that's the
    # whole point of gating ``uv sync``.)
    assert (target / "pyproject.toml").exists()
    assert (target / ".github" / "workflows" / "ci.yml").exists()
    assert (target / "Makefile").exists()
