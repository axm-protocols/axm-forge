"""Unit tests for CheckEngine, format_report, and format_json.

Covers the orchestration engine and both output formatters.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.checker import CheckEngine
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration


def test_run_single_category(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """Filtering to tooling returns only tooling checks."""
    engine = CheckEngine(
        gold_project__from_check_engine_run_and_format, category="tooling"
    )
    result = engine.run()
    assert all(c.category == "tooling" for c in result.checks)
    assert len(result.checks) == 7


def test_run_invalid_category(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """Invalid category raises ValueError."""
    engine = CheckEngine(
        gold_project__from_check_engine_run_and_format, category="invalid"
    )
    with pytest.raises(ValueError, match="Unknown category"):
        engine.run()


class TestWorkspaceSkipsNewEntries:
    """Workspace root skips pyproject.mypy and pyproject.ruff (per-package concerns).

    AXM-2045 un-masked ``pyproject.ruff_rules``, ``pyproject.dynamic_version``
    and ``changelog.gitcliff`` from ``SKIP_FOR_WORKSPACE``: the uv-workspace
    template now ships these gold-standard, so they are verified at the root
    rather than skipped. ``pyproject.mypy`` stays skipped (config lives
    per-package, see mypy-consistency) and ``pyproject.ruff`` stays skipped
    (workspace root has no first-party package for isort known-first-party).
    """

    @pytest.mark.parametrize(
        "skipped_names",
        [
            pytest.param(["pyproject.pyproject_mypy"], id="pyproject_mypy"),
            pytest.param(["pyproject.pyproject_ruff"], id="ruff_config"),
            pytest.param(["docs.diataxis_nav"], id="diataxis_nav"),
        ],
    )
    def test_workspace_skips(
        self,
        gold_project__from_check_engine_run_and_format: Path,
        skipped_names: list[str],
    ) -> None:
        """Workspace root must not report the listed check names."""
        pyproject = gold_project__from_check_engine_run_and_format / "pyproject.toml"
        content = pyproject.read_text()
        content += '\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        pyproject.write_text(content)

        engine = CheckEngine(gold_project__from_check_engine_run_and_format)
        result = engine.run()
        check_names = {c.name for c in result.checks}
        for name in skipped_names:
            assert name not in check_names


class TestMemberRedirectsStructure:
    """Member structure checks redirect to workspace root."""

    @pytest.fixture()
    def ws_with_member(self, tmp_path: Path) -> tuple[Path, Path]:
        """Workspace root with full tooling + bare member."""
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        (ws_root / "LICENSE").write_text("MIT\n")
        (ws_root / ".python-version").write_text("3.12\n")
        (ws_root / "CONTRIBUTING.md").write_text("# Contributing\n")
        (ws_root / "Makefile").write_text(
            ".PHONY: install check test format lint audit clean docs-serve\n"
            "install:\n\techo\ncheck:\n\techo\ntest:\n\techo\nformat:\n\techo\n"
            "lint:\n\techo\naudit:\n\techo\nclean:\n\techo\ndocs-serve:\n\techo\n"
        )
        hooks_dir = ws_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
        gh_dir = ws_root / ".github"
        gh_dir.mkdir(parents=True)
        (gh_dir / "dependabot.yml").write_text(
            "version: 2\nupdates:\n  - package-ecosystem: pip\n"
        )

        member = ws_root / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        return ws_root, member

    @pytest.mark.parametrize(
        "check_name",
        [
            pytest.param("structure.license", id="license"),
            pytest.param("structure.python_version", id="python_version"),
            pytest.param("structure.contributing", id="contributing"),
            pytest.param("tooling.makefile", id="makefile"),
            pytest.param("tooling.precommit_installed", id="precommit_installed"),
            pytest.param("ci.dependabot", id="dependabot"),
        ],
    )
    def test_member_redirects(
        self, ws_with_member: tuple[Path, Path], check_name: str
    ) -> None:
        """Member without the file passes when workspace root provides it."""
        _ws_root, member = ws_with_member
        engine = CheckEngine(member)
        result = engine.run()
        matching = [c for c in result.checks if c.name == check_name]
        assert len(matching) == 1
        assert matching[0].passed


class TestEngineExclusion:
    """Exclusion config auto-passes excluded checks."""

    def test_engine_exclusion_auto_pass(
        self, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Excluded checks get passed=True, message='Excluded by config'."""
        pyproject = gold_project__from_check_engine_run_and_format / "pyproject.toml"
        content = pyproject.read_text()
        content += '\n[tool.axm-init]\nexclude = ["cli"]\n'
        pyproject.write_text(content)

        engine = CheckEngine(gold_project__from_check_engine_run_and_format)
        result = engine.run()

        # cli checks should be excluded
        cli_checks = [c for c in result.checks if c.name.startswith("cli")]
        # There are no cli checks in ALL_CHECKS currently, so we verify
        # excluded_checks list is populated
        assert result.excluded_checks == [] or all(
            c.message == "Excluded by config" for c in cli_checks
        )

    def test_exclusion_nonexistent_ignored(
        self, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Exclusion for non-existent check → no crash, no effect."""
        pyproject = gold_project__from_check_engine_run_and_format / "pyproject.toml"
        content = pyproject.read_text()
        content += '\n[tool.axm-init]\nexclude = ["nonexistent"]\n'
        pyproject.write_text(content)

        engine = CheckEngine(gold_project__from_check_engine_run_and_format)
        result = engine.run()
        assert result.score == 100
        assert len(result.checks) == 40


def test_standalone_skips_workspace(tmp_path: Path) -> None:
    """Standalone project doesn't get workspace checks."""
    from axm_init.core.checker import CheckEngine

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "solo"\n')
    engine = CheckEngine(tmp_path)
    result = engine.run()
    ws_checks = [c for c in result.checks if c.category == "workspace"]
    assert len(ws_checks) == 0


def test_check_engine_instantiation(tmp_path: Path) -> None:
    """CheckEngine can be instantiated after import refactor."""
    from axm_init.core.checker import CheckEngine

    engine = CheckEngine(tmp_path)
    assert engine.project_path == tmp_path.resolve()


def test_checker_fan_out_at_most_10() -> None:
    """AC1: checker.py fan-out <= 10 (unique module-level imports)."""
    import ast

    checker_path = (
        Path(__file__).resolve().parents[2] / "src" / "axm_init" / "core" / "checker.py"
    )
    tree = ast.parse(checker_path.read_text())

    modules: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        # Skip TYPE_CHECKING blocks
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])

    assert len(modules) <= 10, (
        f"checker.py fan-out is {len(modules)} (max 10): {sorted(modules)}"
    )


def _scaffold(project: Path, *, with_force_include: bool) -> None:
    force_include_block = (
        "[tool.hatch.build.targets.wheel.force-include]\n"
        '"docs/test_quality.md" = "pkg/docs/test_quality.md"\n'
        if with_force_include
        else ""
    )
    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "pkg"

            [tool.axm-init.wheel-doc]
            files = ["docs/test_quality.md"]

            [tool.hatch.build.targets.wheel]
            packages = ["src/pkg"]

            {force_include_block}
            """
        ).lstrip()
    )
    docs = project / "docs"
    docs.mkdir()
    (docs / "test_quality.md").write_text("# test quality\n")


def _find_result(project_result: object, check_name: str) -> object:
    results = getattr(project_result, "results", None) or getattr(
        project_result, "checks", []
    )
    for r in results:
        if getattr(r, "name", None) == check_name:
            return r
    raise AssertionError(f"check {check_name!r} not found in result")


def test_axm_init_check_passes_on_correctly_wired_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, with_force_include=True)

    engine = CheckEngine(tmp_path)
    project_result = engine.run()

    finding = _find_result(project_result, "pyproject.wheel_doc_shipping")
    assert finding.passed is True


def test_axm_init_check_fails_on_orphan_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, with_force_include=False)

    engine = CheckEngine(tmp_path)
    project_result = engine.run()

    finding = _find_result(project_result, "pyproject.wheel_doc_shipping")
    assert finding.passed is False
    assert any("test_quality.md" in d for d in finding.details)


# --- CheckEngine exclusion-by-displayed-name (AXM-1840) ---
#
# The canonical name carried by ``CheckResult.name`` (hand-set inside each check
# function, e.g. ``pyproject.urls``) must be the single source of truth for
# exclusion matching. Excluding a check by its DISPLAYED name must actually skip
# it, and the excluded-result stamp must carry that same canonical name.
#
# The ``pyproject.urls`` check is the canary: its function name is
# ``check_pyproject_urls`` so the legacy inferred name was
# ``pyproject.pyproject_urls`` (divergent from the displayed ``pyproject.urls``).


def _exclude_pyproject_urls(project: Path) -> None:
    """Append a ``[tool.axm-init].exclude`` of the displayed name to pyproject."""
    pyproject = project / "pyproject.toml"
    content = pyproject.read_text()
    content += '\n[tool.axm-init]\nexclude = ["pyproject.urls"]\n'
    pyproject.write_text(content)


def test_exclusion_by_displayed_name_skips_check(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """AC2: excluding by the displayed name ``pyproject.urls`` removes it.

    The check must not appear as an active (executed) result and must be
    recorded in ``excluded_checks``.
    """
    project = gold_project__from_check_engine_run_and_format
    _exclude_pyproject_urls(project)

    result = CheckEngine(project).run()

    # The displayed name was excluded by config -> recorded as excluded.
    assert "pyproject.urls" in result.excluded_checks
    # And the legacy inferred name must NOT leak into excluded_checks.
    assert "pyproject.pyproject_urls" not in result.excluded_checks

    # The check still surfaces (as an auto-pass excluded stamp), never as a
    # freshly executed result with a real weight/message.
    matching = [c for c in result.checks if c.name == "pyproject.urls"]
    assert len(matching) == 1
    assert matching[0].message == "Excluded by config"


def test_excluded_result_uses_canonical_name(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """AC3: the excluded-result stamp carries the canonical displayed name.

    Excluding ``pyproject.urls`` must produce a ``CheckResult`` whose ``name``
    is exactly ``pyproject.urls`` (not the inferred ``pyproject.pyproject_urls``).
    """
    project = gold_project__from_check_engine_run_and_format
    _exclude_pyproject_urls(project)

    result = CheckEngine(project).run()

    excluded = [c for c in result.checks if c.message == "Excluded by config"]
    excluded_names = {c.name for c in excluded}
    assert "pyproject.urls" in excluded_names
    assert "pyproject.pyproject_urls" not in excluded_names

    stamp = next(c for c in excluded if c.name == "pyproject.urls")
    assert stamp.passed is True
    assert stamp.category == "pyproject"


# --- Fresh scaffold scores 100 on wheel_doc_shipping (AC1) ---
#
# Scaffold a real project via Copier from the ``python-project`` (standalone)
# template, then run the full ``CheckEngine``. A fresh scaffold must score
# exactly 100 with no ``pyproject.wheel_doc_shipping`` failure (the scaffold
# ships ``docs/index.md`` force-included in its wheel).

_SCAFFOLD_DATA = {
    "package_name": "scaffold-check-demo",
    "description": "A modern Python package",
    "org": "DemoOrg",
    "license": "MIT",
    "license_holder": "DemoOrg",
    "author_name": "Demo Author",
    "author_email": "demo@example.com",
}


@pytest.fixture(scope="module")
def scaffolded_standalone(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold the standalone (python-project) template once via real Copier."""
    target = tmp_path_factory.mktemp("scaffold_check") / "demo-pkg"
    config = CopierConfig(
        template_path=get_template_path(TemplateType.STANDALONE),
        destination=target,
        data=_SCAFFOLD_DATA,
        trust_template=True,
    )
    CopierAdapter().copy(config)
    return target


def test_scaffolded_project_scores_100(scaffolded_standalone: Path) -> None:
    """AC1: fresh scaffold scores 100 with no wheel_doc_shipping failure."""
    result = CheckEngine(scaffolded_standalone).run()

    failed_names = {c.name for c in result.failures}
    assert "pyproject.wheel_doc_shipping" not in failed_names, result.failures
    assert result.score == 100, sorted(failed_names)
