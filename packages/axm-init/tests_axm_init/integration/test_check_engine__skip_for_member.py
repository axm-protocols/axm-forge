"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

import pytest

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


def test_member_skip_does_not_skip_unrelated_check(member_path: Path) -> None:
    """Docs-category checks not in SKIP_FOR_MEMBER still run for member."""
    from axm_init.core.checker import SKIP_FOR_MEMBER

    engine = CheckEngine(member_path)
    result = engine.run()
    docs_checks = {
        c.name
        for c in result.checks
        if c.category == "docs" and c.name not in SKIP_FOR_MEMBER
    }
    assert docs_checks, (
        "member should still run at least one docs check not in SKIP_FOR_MEMBER"
    )


def test_workspace_root_unchanged(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """Workspace root keeps diataxis_nav skip; other SKIP_FOR_MEMBER run."""
    from axm_init.core.checker import SKIP_FOR_MEMBER, SKIP_FOR_WORKSPACE

    pyproject = gold_project__from_check_engine_run_and_format / "pyproject.toml"
    content = pyproject.read_text()
    content += '\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    pyproject.write_text(content)

    engine = CheckEngine(gold_project__from_check_engine_run_and_format)
    result = engine.run()
    check_names = {c.name for c in result.checks}
    assert "docs.diataxis_nav" not in check_names
    for name in SKIP_FOR_MEMBER - SKIP_FOR_WORKSPACE - {"docs.diataxis_nav"}:
        assert name in check_names, f"workspace root must still run {name}"
