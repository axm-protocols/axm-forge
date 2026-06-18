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
            "docs.yml",
            "release.yml",
            "axm-quality.yml.jinja",
            "pre-commit-autoupdate.yml",
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
        tests = member_template / "tests"
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

    def test_mkdocs_is_nav_only(self, member_template: Path) -> None:
        content = (member_template / "mkdocs.yml.jinja").read_text()
        assert "nav:" in content
        # Should NOT have theme/plugins — it's a nav-only config for !include
        assert "plugins:" not in content


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
    def test_dependabot_references_prek(self, template: TemplateType) -> None:
        """AC5: dependabot.yml (when present) references prek, not pre-commit."""
        path = Path(get_template_path(template)) / ".github" / "dependabot.yml"
        if not path.is_file():
            pytest.skip("no dependabot.yml in this template")
        content = path.read_text()
        assert "pre-commit" not in content

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param(TemplateType.STANDALONE, id="standalone"),
            pytest.param(TemplateType.WORKSPACE, id="workspace"),
        ],
    )
    def test_autoupdate_workflow_uses_prek(self, template: TemplateType) -> None:
        """AC5: pre-commit-autoupdate.yml uses prek autoupdate via uv tool install."""
        content = _read(template, ".github", "workflows", "pre-commit-autoupdate.yml")
        assert "uv tool install prek" in content
        assert "prek autoupdate" in content
        assert "pip install pre-commit" not in content
        assert "pre-commit autoupdate" not in content

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
