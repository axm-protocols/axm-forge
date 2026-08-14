"""Integration tests for the context-keyed skip / redirect tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import CheckEngine, _discover_checks, get_check_name

pytestmark = pytest.mark.integration


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table the check engine must expose (AC1)."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(
        checker, "SKIP_BY_CONTEXT", None
    )
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return table


@pytest.fixture()
def member_path(tmp_path: Path) -> Path:
    """Workspace root + bare member package on disk."""
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    (ws_root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = ws_root / "packages" / "foo"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "foo"\n')
    return member


def test_engine_construction_rejects_unregistered_table_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: a bad table id raises ValueError at construction, before any run."""
    bogus = "docs.no_such_check_id"
    table: dict[ProjectContext, frozenset[str]] = dict.fromkeys(
        ProjectContext, frozenset()
    )
    table[ProjectContext.STANDALONE] = frozenset({bogus})
    monkeypatch.setattr(checker, "SKIP_BY_CONTEXT", table, raising=False)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "solo"\n')

    with pytest.raises(ValueError, match=bogus):
        CheckEngine(tmp_path)


def test_member_partition_is_table_driven_and_complete(member_path: Path) -> None:
    """AC5: excluded == member table entry, disjoint from executed, union = all."""
    member_skips = set(_skip_table()[ProjectContext.MEMBER])

    engine = CheckEngine(member_path)
    assert engine.context == ProjectContext.MEMBER
    result = engine.run()
    executed = {c.name for c in result.checks}
    discovered = {
        get_check_name(fn) for fns in _discover_checks().values() for fn in fns
    }
    excluded = discovered - executed

    assert excluded == member_skips
    assert excluded.isdisjoint(executed)
    assert excluded | executed == discovered


def test_module_source_drops_the_legacy_constants() -> None:
    """AC6: the three legacy identifiers are gone from the engine source."""
    source = Path(checker.__file__).read_text(encoding="utf-8")

    for legacy in ("SKIP_FOR_WORKSPACE", "SKIP_FOR_MEMBER", "REDIRECT_FOR_MEMBER"):
        assert legacy not in source, f"{legacy} still defined in {checker.__file__}"
