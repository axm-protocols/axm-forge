"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import CheckEngine


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table the check engine must expose (AC1)."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(
        checker, "SKIP_BY_CONTEXT", None
    )
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return table


@pytest.fixture()
def member_path(tmp_path: Path) -> Path:
    """Workspace root + bare member package."""
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    (ws_root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = ws_root / "packages" / "foo"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "foo"\n')
    return member


def test_member_skips_skip_for_member(member_path: Path) -> None:
    """Member result must not contain any SKIP_FOR_MEMBER check name."""
    skipped = _skip_table()[ProjectContext.MEMBER]

    engine = CheckEngine(member_path)
    assert engine.context == ProjectContext.MEMBER
    result = engine.run()
    check_names = {c.name for c in result.checks}
    for skip_name in skipped:
        assert skip_name not in check_names, f"{skip_name} should be skipped for member"


def test_standalone_runs_skip_for_member_checks(tmp_path: Path) -> None:
    """Standalone projects must still run all SKIP_FOR_MEMBER checks."""
    skip_table = _skip_table()

    standalone = tmp_path / "solo"
    standalone.mkdir()
    (standalone / "pyproject.toml").write_text('[project]\nname = "solo"\n')

    engine = CheckEngine(standalone)
    assert engine.context == ProjectContext.STANDALONE
    result = engine.run()
    check_names = {c.name for c in result.checks}
    member_only = (
        skip_table[ProjectContext.MEMBER] - skip_table[ProjectContext.STANDALONE]
    )
    for required in member_only:
        assert required in check_names, f"standalone must still run {required}"
