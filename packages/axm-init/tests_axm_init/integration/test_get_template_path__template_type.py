"""Tests for workspace scaffold template and TemplateType.

Also hosts the prek-migration scenario (AXM-2056) — those tests share the same
two covered symbols (``get_template_path`` + ``TemplateType``) but spread across
several canonical tuples, which the file-naming rule flags as a SPLIT; the file
is a deliberately cohesive template-source suite, exempted via
``scenario_name_ok``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.scenario_name_ok


def _read(template: TemplateType, *parts: str) -> str:
    """Read a file from the packaged *template* tree as text."""
    path = Path(get_template_path(template)).joinpath(*parts)
    return path.read_text()


@pytest.mark.parametrize(
    ("template_type", "expected_name"),
    [
        pytest.param(TemplateType.WORKSPACE, "uv-workspace", id="workspace"),
        pytest.param(TemplateType.MEMBER, "workspace-member", id="member"),
    ],
)
def test_template_path_resolves_to_named_directory(
    template_type: TemplateType, expected_name: str
) -> None:
    path = get_template_path(template_type)
    assert path.name == expected_name
    assert path.is_dir()


@pytest.mark.parametrize(
    "template_type",
    [
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
        pytest.param(TemplateType.MEMBER, id="member"),
    ],
)
def test_template_has_copier_yml(template_type: TemplateType) -> None:
    path = get_template_path(template_type)
    assert (path / "copier.yml").is_file()


@pytest.mark.integration
def test_paper_template_path_resolves_to_named_directory() -> None:
    with pytest.raises(ValueError, match="axm-lab"):
        get_template_path(TemplateType.PAPER)


@pytest.mark.integration
def test_experiment_template_path_resolves_to_named_directory() -> None:
    with pytest.raises(KeyError):
        get_template_path(TemplateType.EXPERIMENT)


class TestWorkspaceTemplateStructure:
    """Verify workspace template includes all required files."""

    @pytest.fixture()
    def ws_template(self) -> Path:
        return get_template_path(TemplateType.WORKSPACE)

    def test_root_files(self, ws_template: Path) -> None:
        for name in [
            "copier.yml",
            "pyproject.toml.jinja",
            "Makefile",
            "README.md.jinja",
            "CONTRIBUTING.md.jinja",
            ".gitignore",
            ".pre-commit-config.yaml.jinja",
            "cliff.toml",
        ]:
            assert (ws_template / name).exists(), f"Missing {name}"

    def test_docs_files(self, ws_template: Path) -> None:
        assert (ws_template / "mkdocs.yml.jinja").is_file()
        assert (ws_template / "docs" / "index.md.jinja").is_file()
        assert (ws_template / "docs" / "gen_ref_pages.py").is_file()

    def test_ci_workflows(self, ws_template: Path) -> None:
        ci = ws_template / ".github" / "workflows"
        for name in [
            "ci.yml.jinja",
            "publish.yml",
            # Templated, not static: its body branches on `docs_hosting`
            # (GitHub Pages by default, Cloudflare on request).
            "docs.yml.jinja",
            "release.yml",
            "axm-quality.yml.jinja",
        ]:
            assert (ci / name).exists(), f"Missing CI workflow: {name}"

    def test_dependabot(self, ws_template: Path) -> None:
        assert (ws_template / ".github" / "dependabot.yml").is_file()

    def test_pyproject_has_workspace_config(self, ws_template: Path) -> None:
        content = (ws_template / "pyproject.toml.jinja").read_text()
        assert "[tool.uv.workspace]" in content
        assert 'members = ["packages/*"]' in content

    def test_mkdocs_has_monorepo(self, ws_template: Path) -> None:
        content = (ws_template / "mkdocs.yml.jinja").read_text()
        assert "monorepo" in content

    def test_ci_uses_package_flag(self, ws_template: Path) -> None:
        ci = ws_template / ".github" / "workflows" / "ci.yml.jinja"
        content = ci.read_text()
        assert "--package" in content

    def test_ci_has_no_root_level_pytest_job(self, ws_template: Path) -> None:
        """No job may run the suite from the workspace root.

        A `coverage` job used to do exactly that (`pytest packages/` after a
        bare `uv sync`). A bare sync installs no member, so every test failed
        on ModuleNotFoundError and coverage fell under the gate — a red CI on
        a freshly scaffolded, otherwise correct workspace.
        """
        content = (ws_template / ".github" / "workflows" / "ci.yml.jinja").read_text()
        # Commands only: the comment explaining why this job is gone names the
        # very invocation it forbids.
        commands = [
            line for line in content.splitlines() if not line.lstrip().startswith("#")
        ]
        assert not [line for line in commands if "pytest packages/" in line]

    def test_ci_syncs_all_packages(self, ws_template: Path) -> None:
        """Every job installs the members before acting on them.

        A bare `uv sync` resolves the root only: ruff would lint sources whose
        dependencies are absent and pip-audit would audit none of the members'
        dependencies.
        """
        content = (ws_template / ".github" / "workflows" / "ci.yml.jinja").read_text()
        sync_lines = [
            line.strip()
            for line in content.splitlines()
            if "uv sync" in line and not line.strip().startswith("#")
        ]
        assert sync_lines, "expected at least one uv sync step"
        assert all("--all-packages" in line for line in sync_lines), sync_lines

    def test_docs_workflow_syncs_members_and_docs_group(
        self, ws_template: Path
    ) -> None:
        """The docs build needs both flags, and each one alone fails.

        `--group docs` installs mkdocs itself; `--all-packages` keeps the
        members importable, since mkdocstrings imports each one to render its
        API reference.
        """
        content = (ws_template / ".github" / "workflows" / "docs.yml.jinja").read_text()
        sync_lines = [line for line in content.splitlines() if "uv sync" in line]
        assert sync_lines, "expected a uv sync step"
        for line in sync_lines:
            assert "--all-packages" in line, line
            assert "--group docs" in line, line

    def test_docs_workflow_offers_both_hosts(self, ws_template: Path) -> None:
        """GitHub Pages is the default; Cloudflare is opt-in.

        Pages needs no secret, so a scaffolded workspace publishes on its
        first push. Cloudflare matches the existing AXM workspaces but
        requires CLOUDFLARE_* secrets, so it stays a deliberate choice.
        """
        content = (ws_template / ".github" / "workflows" / "docs.yml.jinja").read_text()
        assert "docs_hosting == 'cloudflare'" in content
        assert "upload-pages-artifact" in content
        assert "wrangler-action" in content

    def test_root_ref_generator_writes_member_api_paths(
        self, ws_template: Path
    ) -> None:
        """The root generator emits pages where each member's nav expects them.

        `monorepo` merges the members' nav but does not run their plugins, so
        the root regenerates their reference. It must write under
        `<member>/reference/api/`: an earlier version wrote to
        `reference/<module>/`, producing pages no nav referenced plus a
        "not found in the documentation files" warning per member.
        """
        content = (ws_template / "docs" / "gen_ref_pages.py").read_text()
        # Both the module pages and the literate-nav SUMMARY must carry the
        # member prefix and the `api` segment. Asserting on the file as a
        # whole would let one of the two regress unnoticed while the other
        # keeps the string alive.
        page_line = next(
            line
            for line in content.splitlines()
            if "full_doc_path = " in line and "with_suffix" not in line
        )
        assert '"reference", "api"' in page_line, page_line
        assert "pkg_dir.name" in page_line, page_line

        summary_line = next(
            line for line in content.splitlines() if "summary = " in line
        )
        assert '"reference", "api"' in summary_line, summary_line
        assert "pkg_dir.name" in summary_line, summary_line


class TestMemberTemplateStructure:
    """Verify workspace-member template includes all required files."""

    @pytest.fixture()
    def member_template(self) -> Path:
        return get_template_path(TemplateType.MEMBER)

    def test_root_files(self, member_template: Path) -> None:
        for name in [
            "copier.yml",
            "pyproject.toml.jinja",
            "README.md.jinja",
            "CONTRIBUTING.md.jinja",
            "mkdocs.yml.jinja",
        ]:
            assert (member_template / name).exists(), f"Missing {name}"

    def test_src_files(self, member_template: Path) -> None:
        src = member_template / "src" / "{{module_name}}"
        assert (src / "__init__.py.jinja").is_file()
        assert (src / "py.typed").is_file()

    def test_test_files(self, member_template: Path) -> None:
        # Nom dérivé du membre : on cherche la suite, pas un littéral.
        tests = next(d for d in member_template.glob("tests_*") if d.is_dir())
        assert (tests / "__init__.py").is_file()
        assert (tests / "conftest.py").is_file()

    def test_docs_files(self, member_template: Path) -> None:
        assert (member_template / "docs" / "index.md.jinja").is_file()

    @pytest.mark.parametrize(
        "needle",
        [
            pytest.param("hatch-vcs", id="hatch_vcs"),
            pytest.param("tag-pattern", id="tag_pattern"),
            pytest.param("{{ member_name }}", id="member_name"),
        ],
    )
    def test_pyproject_contains(self, member_template: Path, needle: str) -> None:
        content = (member_template / "pyproject.toml.jinja").read_text()
        assert needle in content

    def test_mkdocs_is_standalone_buildable(self, member_template: Path) -> None:
        """Member mkdocs ships theme + plugins so `--strict` builds standalone.

        AXM-19: the member config was previously nav-only (no plugins), which
        made `mkdocs build --strict` abort standalone on the `reference/api/`
        nav entry (green only under the monorepo-root `!include` aggregation).
        The member now carries its own material theme + gen-files/literate-nav/
        mkdocstrings plugins, and a `docs/gen_ref_pages.py.jinja` generator.
        """
        content = (member_template / "mkdocs.yml.jinja").read_text()
        assert "nav:" in content
        assert "theme:" in content
        assert "plugins:" in content
        for plugin in ("gen-files", "literate-nav", "mkdocstrings"):
            assert plugin in content, f"member mkdocs must declare {plugin}"
        assert (member_template / "docs" / "gen_ref_pages.py.jinja").is_file()


class TestPrekMigration:
    """Templates migrated from pre-commit to prek (AXM-2056).

    These tests read the real template files shipped under
    ``axm_init.templates`` via ``get_template_path`` (real I/O on the packaged
    template tree) and assert on their content, so a future drift back to
    ``pre-commit`` fails here. They cover the template *source*; the
    scaffolded-output behaviour is covered in ``test_scaffold_flow_via_cli.py``.
    """

    @pytest.mark.parametrize(
        ("template", "parts", "needle"),
        [
            pytest.param(
                TemplateType.STANDALONE,
                ("pyproject.toml.jinja",),
                '"prek>=',
                id="standalone-pyproject-pins",
            ),
            pytest.param(
                TemplateType.WORKSPACE,
                ("pyproject.toml.jinja",),
                '"prek>=',
                id="workspace-pyproject-pins",
            ),
            pytest.param(
                TemplateType.MEMBER,
                ("pyproject.toml.jinja",),
                '"prek>=',
                id="member-pyproject-pins",
            ),
            pytest.param(
                TemplateType.WORKSPACE,
                ("copier.yml",),
                "uv run prek install",
                id="workspace-copier-installs",
            ),
            pytest.param(
                TemplateType.WORKSPACE,
                ("CONTRIBUTING.md.jinja",),
                "uv run prek install",
                id="workspace-contributing-mentions",
            ),
        ],
    )
    def test_template_file_uses_prek_not_precommit(
        self, template: TemplateType, parts: tuple[str, ...], needle: str
    ) -> None:
        """AC1-AC3: each migrated template file carries its prek marker (version
        pin in pyproject, ``uv run prek install`` in copier/CONTRIBUTING) and no
        longer mentions pre-commit."""
        content = _read(template, *parts)
        assert needle in content
        assert "pre-commit" not in content

    def test_standalone_copier_installs_prek(self) -> None:
        """AC1: python-project copier tasks add prek and run prek install."""
        content = _read(TemplateType.STANDALONE, "copier.yml")
        assert "uv run prek install" in content
        assert " prek " in content  # `uv add --group dev ... prek ...`
        assert "pre-commit" not in content

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param(TemplateType.STANDALONE, id="standalone"),
            pytest.param(TemplateType.WORKSPACE, id="workspace"),
        ],
    )
    def test_dependabot_does_not_invoke_precommit(self, template: TemplateType) -> None:
        """AC5: dependabot.yml never invokes the abandoned pre-commit TOOL.

        The bare string ``pre-commit`` stopped being a useful marker: prek reads
        the very same ``.pre-commit-config.yaml``, and Dependabot names
        ``pre-commit`` the ECOSYSTEM that tracks the ``rev:`` of that format —
        it only parses the YAML and queries each hook repository for new tags,
        never running either tool. Forbidding the substring would forbid naming
        the file we actually use. Only invocations of the abandoned tool are.
        """
        path = Path(get_template_path(template)) / ".github" / "dependabot.yml"
        if not path.is_file():
            pytest.skip("no dependabot.yml in this template")
        content = path.read_text()
        for invocation in (
            "pip install pre-commit",
            "pre-commit run",
            "pre-commit autoupdate",
            "pre-commit install",
        ):
            assert invocation not in content

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param(TemplateType.STANDALONE, id="standalone"),
            pytest.param(TemplateType.WORKSPACE, id="workspace"),
        ],
    )
    def test_no_autoupdate_cron_workflow(self, template: TemplateType) -> None:
        """The hook `rev:` is tracked by Dependabot, not by a scheduled workflow.

        A `prek autoupdate` cron duplicated what the `pre-commit` Dependabot
        ecosystem does natively since 2026-03-10 — and did it worse: no
        changelog in the PR, and no branch cleanup, which left orphaned
        branches behind on every workspace that shipped it. axm-forge never
        carried one. The scaffold must not recreate it beside the ecosystem
        block now declared in dependabot.yml.
        """
        workflows = Path(get_template_path(template)) / ".github" / "workflows"
        assert not (workflows / "pre-commit-autoupdate.yml").exists()
        assert not (workflows / "prek-autoupdate.yml").exists()

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param(TemplateType.STANDALONE, id="standalone"),
            pytest.param(TemplateType.WORKSPACE, id="workspace"),
        ],
    )
    def test_precommit_config_template_source_is_jinja(
        self, template: TemplateType
    ) -> None:
        """AC4/AC6: template SOURCE is .pre-commit-config.yaml.jinja, not literal."""
        root = Path(get_template_path(template))
        assert (root / ".pre-commit-config.yaml.jinja").is_file()
        assert not (root / ".pre-commit-config.yaml").exists()
