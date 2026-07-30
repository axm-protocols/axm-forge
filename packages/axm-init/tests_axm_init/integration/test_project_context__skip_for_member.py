"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core.checker import CheckEngine


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
    from axm_init.core.checker import SKIP_FOR_MEMBER

    engine = CheckEngine(member_path)
    assert engine.context == ProjectContext.MEMBER
    result = engine.run()
    check_names = {c.name for c in result.checks}
    for skip_name in SKIP_FOR_MEMBER:
        assert skip_name not in check_names, f"{skip_name} should be skipped for member"


def test_standalone_runs_skip_for_member_checks(tmp_path: Path) -> None:
    """Standalone projects must still run all SKIP_FOR_MEMBER checks."""
    from axm_init.core.checker import SKIP_FOR_MEMBER

    standalone = tmp_path / "solo"
    standalone.mkdir()
    (standalone / "pyproject.toml").write_text('[project]\nname = "solo"\n')

    engine = CheckEngine(standalone)
    assert engine.context == ProjectContext.STANDALONE
    result = engine.run()
    check_names = {c.name for c in result.checks}
    for required in SKIP_FOR_MEMBER:
        assert required in check_names, f"standalone must still run {required}"
