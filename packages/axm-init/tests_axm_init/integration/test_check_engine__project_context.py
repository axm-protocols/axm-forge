"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import ALL_CHECKS, CheckEngine, get_check_name
from axm_init.models.check import ProjectResult


class TestEngineMember:
    """Member context redirects CI/tooling to workspace root."""

    def test_engine_member_redirects_ci(
        self, tmp_path: Path, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Member CI checks run against workspace root."""
        # Create workspace structure: tmp_path is workspace root
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        (ws_root / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )

        # Create member package
        member = ws_root / "packages" / "pkg"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        engine = CheckEngine(member)
        assert engine.context == ProjectContext.MEMBER
        assert engine.workspace_root == ws_root


# --- paper context: packaging checks out, paper checks in -----------------

PAPER_CHECK_IDS = frozenset({"paper.paper_structure", "paper.plan_present"})

# Python-packaging documentation ids a paper must never be graded on.
PACKAGING_DOC_CHECK_IDS = frozenset(
    {
        "docs.diataxis_nav",
        "docs.gen_ref_pages",
        "docs.mkdocs_exists",
        "docs.plugins",
        "docs.readme_badges",
        "docs.standalone_api_ref",
    }
)


def _discovered_ids() -> set[str]:
    """Every canonical check id the discovery registry currently exposes."""
    names = {get_check_name(fn) for fns in ALL_CHECKS.values() for fn in fns}
    return {name for name in names if name is not None}


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table the check engine must expose."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(
        checker, "SKIP_BY_CONTEXT", None
    )
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return table


def _ran_ids(result: ProjectResult) -> set[str]:
    """The ids the engine actually ran (i.e. NOT excluded) for this project."""
    for attr in ("checks", "results", "check_results"):
        value = getattr(result, attr, None)
        if isinstance(value, list):
            return {check.name for check in value}
    msg = "ProjectResult must expose the list of check results it ran"
    raise AssertionError(msg)


def _excluded_ids(result: ProjectResult) -> set[str]:
    """Ids with status excluded: skipped by context, or excluded by config."""
    explicit = set(getattr(result, "excluded_checks", None) or ())
    return (_discovered_ids() - _ran_ids(result)) | explicit


def _paper_project(root: Path) -> Path:
    """Hand-build a paper: axm-lab marker, paper tree, plan with front-matter."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-x"\nversion = "0.1.0"\n\n'
        '[tool.axm-lab]\nslug = "paper-x"\n'
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper X\n")
    (root / "plan.md").write_text("---\ntitle: Paper X\nstatus: draft\n---\n\n# Plan\n")
    return root


@pytest.mark.integration
def test_paper_project_excludes_every_packaging_check(tmp_path: Path) -> None:
    """AC4: packaging ids are excluded on a paper and no packaging failure remains."""
    project = _paper_project(tmp_path / "paper-x")

    engine = CheckEngine(project)
    result = engine.run()

    assert engine.context == ProjectContext.PAPER
    assert PACKAGING_DOC_CHECK_IDS <= _excluded_ids(result)
    packaging_failures = {
        check.name for check in result.failures if not check.name.startswith("paper.")
    }
    assert packaging_failures == set()


@pytest.mark.integration
def test_paper_project_runs_both_paper_checks(tmp_path: Path) -> None:
    """AC5: check_paper_structure and check_plan_present both run on a paper."""
    project = _paper_project(tmp_path / "paper-x")

    result = CheckEngine(project).run()

    assert PAPER_CHECK_IDS <= _ran_ids(result)
    assert PAPER_CHECK_IDS & _excluded_ids(result) == set()


@pytest.mark.integration
def test_legacy_contexts_keep_their_exact_non_excluded_id_sets(
    tmp_path: Path,
) -> None:
    """AC6: each legacy context runs exactly its expected id set, paper ids out."""
    standalone = tmp_path / "standalone"
    standalone.mkdir()
    (standalone / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = workspace / "packages" / "pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    skip_table = _skip_table()
    discovered = _discovered_ids()

    for project, context in (
        (standalone, ProjectContext.STANDALONE),
        (workspace, ProjectContext.WORKSPACE),
        (member, ProjectContext.MEMBER),
    ):
        engine = CheckEngine(project)
        assert engine.context == context
        result = engine.run()

        expected = discovered - set(skip_table[context])
        assert _ran_ids(result) == expected
        assert PAPER_CHECK_IDS <= set(skip_table[context])
        assert PAPER_CHECK_IDS & _ran_ids(result) == set()
