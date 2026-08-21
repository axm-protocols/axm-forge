"""Integration tests for the context-keyed skip / redirect tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.checks.docs import check_mkdocs_exists
from axm_init.checks.experiment import (
    check_experiment_files,
    check_experiment_structure,
)
from axm_init.checks.pyproject import check_pyproject_exists
from axm_init.checks.structure import (
    check_py_typed,
    check_src_layout,
    check_tests_dir,
)
from axm_init.core import checker
from axm_init.core.checker import CheckEngine, _discover_checks, get_check_name
from axm_init.tools.scaffold import InitScaffoldTool

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


def _experiment_check_ids() -> set[str]:
    # Canonical ids of the two experiment form checks.
    ids: set[str] = set()
    for fn in (check_experiment_structure, check_experiment_files):
        name = get_check_name(fn)
        assert name is not None
        ids.add(name)
    return ids


def _make_standalone(tmp_path: Path) -> Path:
    # A bare standalone package on disk.
    solo = tmp_path / "solo"
    solo.mkdir()
    (solo / "pyproject.toml").write_text('[project]\nname = "solo"\n')
    return solo


def _make_workspace_root(tmp_path: Path) -> Path:
    # A bare uv workspace root on disk.
    root = tmp_path / "wsroot"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "wsroot"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    return root


def _make_paper(tmp_path: Path) -> Path:
    # A paper folder on disk (no experiment manifest at its root).
    paper = tmp_path / "paper_proj"
    (paper / "paper").mkdir(parents=True)
    (paper / "experiments").mkdir()
    (paper / "README.md").write_text("# paper\n")
    (paper / "PIPELINE.md").write_text("# pipeline\n")
    (paper / "PLAN.md").write_text("---\ntitle: demo\n---\n\n# plan\n")
    return paper


def test_experiment_checks_are_skipped_for_every_non_experiment_context() -> None:
    # AC3: both experiment ids sit in the skip entry of every other context.
    table = _skip_table()
    ids = _experiment_check_ids()

    for context in ProjectContext:
        if context is ProjectContext.EXPERIMENT:
            continue
        assert ids <= set(table[context]), context

    assert ids.isdisjoint(table[ProjectContext.EXPERIMENT])


def test_research_check_shares_the_paper_partition() -> None:
    # AC4: the new paper check is registered in the context tables exactly
    # where its sibling paper.plan_present is - same skip entry per context.
    table = _skip_table()
    skipped_for_plan = {
        context for context in ProjectContext if "paper.plan_present" in table[context]
    }
    assert skipped_for_plan, "paper.plan_present must be skipped somewhere"

    skipped_for_research = {
        context
        for context in ProjectContext
        if "paper.research_present" in table[context]
    }

    assert skipped_for_research == skipped_for_plan


def test_experiment_checks_never_run_outside_an_experiment(
    tmp_path: Path,
    member_path: Path,
) -> None:
    # AC3: standalone, workspace, member and paper never see them at all.
    ids = _experiment_check_ids()
    discovered = {
        get_check_name(fn) for fns in _discover_checks().values() for fn in fns
    }
    assert ids <= discovered

    projects = (
        _make_standalone(tmp_path),
        _make_workspace_root(tmp_path),
        member_path,
        _make_paper(tmp_path),
    )
    for project in projects:
        result = CheckEngine(project).run()
        assert ids.isdisjoint({c.name for c in result.checks}), project


SCAFFOLD_IDENTITY = {
    "org": "DemoOrg",
    "author": "Demo Author",
    "email": "demo@example.com",
}


def _packaging_check_ids() -> set[str]:
    # Canonical ids of the five Python-packaging checks.
    return {
        name
        for fn in (
            check_pyproject_exists,
            check_src_layout,
            check_py_typed,
            check_tests_dir,
            check_mkdocs_exists,
        )
        if (name := get_check_name(fn)) is not None
    }


@pytest.fixture()
def experiment_path(tmp_path: Path) -> Path:
    # A real experiment folder, scaffolded inside a real paper on disk.
    paper = tmp_path / "demo-paper"
    paper.mkdir()
    tool = InitScaffoldTool()
    bootstrap = tool.execute(
        path=str(paper),
        kind="paper",
        name="demo-paper",
        **SCAFFOLD_IDENTITY,
    )
    assert bootstrap.success, bootstrap.error
    made = tool.execute(
        path=str(paper),
        kind="experiment",
        name="baseline",
        **SCAFFOLD_IDENTITY,
    )
    assert made.success, made.error
    assert isinstance(made.data, dict)
    return Path(str(made.data["path"]))


def test_packaging_checks_never_fail_for_an_experiment(
    experiment_path: Path,
) -> None:
    # AC2: on an experiment the packaging checks are skipped, never failed.
    engine = CheckEngine(experiment_path)
    assert engine.context == ProjectContext.EXPERIMENT

    result = engine.run()
    packaging = _packaging_check_ids()

    assert packaging.isdisjoint({f.name for f in result.failures})
    for check in result.checks:
        if check.name in packaging:
            assert check.passed, check.message


def test_experiment_form_checks_run_and_pass(experiment_path: Path) -> None:
    # AC3: the two form checks execute and pass on an experiment folder,
    # while the packaging rulebook does not run at all.
    result = CheckEngine(experiment_path).run()
    executed = {check.name: check for check in result.checks}
    form_ids = _experiment_check_ids()

    assert form_ids <= set(executed)
    assert all(executed[name].passed for name in form_ids), result.failures
    assert _packaging_check_ids().isdisjoint(executed)
