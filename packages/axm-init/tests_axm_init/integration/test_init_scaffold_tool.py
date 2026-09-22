"""Split from ``test_scaffold_tool_error_paths_and_member.py``."""

import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult

from axm_init.tools.scaffold import InitScaffoldTool
from tests_axm_init.conftest import (
    materialize_post_copy_artifacts,
    scaffold_without_tasks,
)


class TestScaffoldExecuteException:
    """Cover lines 173-174: exception in execute."""

    def test_copier_exception_caught(self, tmp_path: Path) -> None:
        """Exception from CopierAdapter → ToolResult(success=False)."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        with patch(
            "axm_init.adapters.copier.CopierAdapter",
            side_effect=RuntimeError("copier broke"),
        ):
            result = tool.execute(
                path=str(tmp_path),
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "copier broke" in (result.error or "")


class TestScaffoldExecuteMissingTemplate:
    """Cover template error path."""

    def test_get_template_path_error(self, tmp_path: Path) -> None:
        """Non-existent template → exception caught."""
        from axm_init.tools.scaffold import InitScaffoldTool

        tool = InitScaffoldTool()
        with patch(
            "axm_init.core.templates.get_template_path",
            side_effect=FileNotFoundError("template not found"),
        ):
            result = tool.execute(
                path=str(tmp_path),
                org="myorg",
                author="Author",
                email="a@b.com",
            )
        assert result.success is False
        assert "template not found" in (result.error or "")


@pytest.fixture()
def scaffold_tool() -> InitScaffoldTool:
    return InitScaffoldTool()


@pytest.fixture()
def base_kwargs() -> dict[str, Any]:
    """Minimal kwargs required by scaffold tool."""
    return {
        "org": "test-org",
        "author": "Test Author",
        "email": "test@example.com",
    }


class TestScaffoldToolMemberMode:
    """AC3: InitScaffoldTool accepts member kwarg."""

    def test_scaffold_tool_member_mode(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        # Create a workspace structure
        ws_root = tmp_path
        pyproject = ws_root / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-ws"\n\n'
            "[tool.uv.workspace]\n"
            'members = ["packages/*"]\n'
        )
        (ws_root / "Makefile").write_text("test-all:\n\techo test\n")
        (ws_root / "mkdocs.yml").write_text(
            "site_name: test\nnav:\n  - Home: index.md\n"
        )
        ci_dir = ws_root / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "ci.yml").write_text(
            "jobs:\n  test:\n    strategy:\n      matrix:\n"
            "        package:\n          - existing\n"
            "    steps:\n      - run: echo test\n"
        )
        publish_content = (
            "name: Publish\non:\n  push:\n"
            '    tags:\n      - "v*"\n'
            "jobs:\n  pub:\n    runs-on: ubuntu-latest\n"
        )
        (ci_dir / "publish.yml").write_text(publish_content)

        base_kwargs["path"] = str(ws_root)
        base_kwargs["member"] = "my-lib"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [Path("pyproject.toml")]

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_copier_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_copier_cls.return_value = mock_copier

            tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is True
        assert tool_result.data is not None
        assert tool_result.data["member"] == "my-lib"
        assert "patched_root_files" in tool_result.data

    def test_scaffold_member_not_in_workspace(
        self,
        scaffold_tool: InitScaffoldTool,
        tmp_path: Path,
        base_kwargs: dict[str, Any],
    ) -> None:
        """Member scaffold fails outside workspace."""
        base_kwargs["path"] = str(tmp_path)
        base_kwargs["member"] = "my-lib"

        tool_result = scaffold_tool.execute(**base_kwargs)

        assert tool_result.success is False
        assert "workspace" in (tool_result.error or "").lower()


EXPERIMENT_IDENTITY = {
    "org": "test-org",
    "author": "Test Author",
    "email": "test@example.com",
}


PROTOCOL_DECLARATION: dict[str, object] = {
    "domain": "dev",
    "unit": "work",
    "action": "create",
    "contracts": [{"name": "brief"}],
    "prompts": [{"name": "author", "text": "Author the work."}],
    "nodes": [{"name": "author", "contract": "brief", "prompt": "author"}],
    "phases": [{"name": "draft", "nodes": ["author"]}],
    "ticket": {"ticket_type": "dev.work", "input_contract": "brief"},
}


def _tree_snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode,
            path.stat().st_mtime_ns,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def _scaffold_without_tasks(path: Path, **kwargs: object) -> ToolResult:
    """Run the scaffold tool with the templates' post-copy tasks disabled.

    Thin wrapper over the shared :func:`scaffold_without_tasks` block: it adds
    this module's identity defaults and synthesizes the post-copy artifacts at
    whichever root the tool reports (a member lands under ``packages/<name>``,
    not at the requested path).
    """
    with scaffold_without_tasks():
        result = InitScaffoldTool().execute(
            path=str(path),
            **{**EXPERIMENT_IDENTITY, **kwargs},
        )

    reported = (result.data or {}).get("root") or (result.data or {}).get("path")
    rendered = Path(str(reported)) if reported else path
    if (rendered / "pyproject.toml").is_file():
        materialize_post_copy_artifacts(rendered)
    return result


@pytest.mark.integration
def test_python_package_and_member_register_protocol_profile(tmp_path: Path) -> None:
    """AC1: both Python modes expose their derived distribution and location.

    Renders with ``skip_tasks=True``: this contract reads only the structured
    result and the merged ``pyproject.toml``, never an artifact the post-copy
    tasks produce, so running them would resolve and install 72 packages three
    times over for nothing (measured: 5.5s and 366 MB against 0.3s here).
    """
    package_root = tmp_path / "protocols-dev"
    package = _scaffold_without_tasks(
        package_root,
        name="protocols-dev",
        profile="protocols",
        domain="dev",
        protocols=[],
    )
    assert package.success, package.error
    assert package.data is not None
    assert package.data["profile"] == "protocols"
    assert package.data["mode"] == "standalone"
    assert package.data["distribution"] == "protocols-dev"
    assert package.data["root"] == str(package_root)
    assert "[tool.axm-init.protocols]" in (package_root / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    workspace_root = tmp_path / "workspace"
    workspace = _scaffold_without_tasks(
        workspace_root,
        name="protocol-workspace",
        workspace=True,
    )
    assert workspace.success, workspace.error
    member = _scaffold_without_tasks(
        workspace_root,
        member="protocols-research",
        profile="protocols",
        domain="research",
        protocols=[],
    )
    assert member.success, member.error
    assert member.data is not None
    assert member.data["profile"] == "protocols"
    assert member.data["mode"] == "member"
    assert member.data["distribution"] == "protocols-research"
    expected_root = workspace_root / "packages" / "protocols-research"
    assert member.data["root"] == str(expected_root)
    assert "[tool.axm-init.protocols]" in (expected_root / "pyproject.toml").read_text(
        encoding="utf-8"
    )


@pytest.mark.integration
def test_protocol_unit_preview_is_exact_and_has_no_side_effect(
    tmp_path: Path,
) -> None:
    """AC2: preview reports the planner paths and leaves bytes/metadata intact."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        # The target owns the profile up front: a unit/protocol request
        # refuses a package that declares none rather than registering one.
        '[project]\nname = "protocols-dev"\nversion = "0.1.0"\n'
        '\n[tool.axm-init.protocols]\nschema_version = 1\ndomain = "dev"\n',
        encoding="utf-8",
    )
    before = _tree_snapshot(tmp_path)

    result = InitScaffoldTool().execute(
        path=str(tmp_path),
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[PROTOCOL_DECLARATION],
        preview=True,
        **EXPERIMENT_IDENTITY,
    )

    assert result.success, result.error
    assert result.data is not None
    assert result.data["preview"] is True
    assert result.data["profile"] == "protocols"
    assert result.data["mode"] == "unit"
    assert result.data["root"] == str(tmp_path)
    assert result.data["protocols"] == ["dev.work.create"]
    expected = {
        "src/protocols_dev/__init__.py",
        "src/protocols_dev/work/__init__.py",
        "src/protocols_dev/work/create/__init__.py",
        "src/protocols_dev/work/create/contracts/__init__.py",
        "src/protocols_dev/work/create/contracts/brief.py",
        "src/protocols_dev/work/create/nodes/__init__.py",
        "src/protocols_dev/work/create/nodes/author.py",
        "src/protocols_dev/work/create/phases/__init__.py",
        "src/protocols_dev/work/create/phases/draft.py",
        "src/protocols_dev/work/create/prompts/__init__.py",
        "src/protocols_dev/work/create/prompts/author.md",
        "src/protocols_dev/work/create/protocol.py",
        "src/protocols_dev/work/create/ticket.py",
    }
    planned = set().union(
        result.data["created"],
        result.data["updated"],
        result.data["unchanged"],
        result.data["conflicts"],
    )
    assert planned == expected
    assert _tree_snapshot(tmp_path) == before


@pytest.mark.integration
def test_invalid_protocol_requests_fail_before_any_effect(tmp_path: Path) -> None:
    """AC4: every invalid combination names its reason and is atomic."""
    cases = (
        (
            {"domain": "dev", "protocols": [PROTOCOL_DECLARATION]},
            "profile",
        ),
        (
            {"profile": "protocols", "domain": "dev", "unit": "work", "protocols": []},
            "protocols",
        ),
        (
            {
                "profile": "protocols",
                "framework": "node",
                "domain": "dev",
                "unit": "work",
                "protocols": [PROTOCOL_DECLARATION],
            },
            "python",
        ),
        (
            {
                "profile": "protocols",
                "domain": "dev",
                "protocols": [PROTOCOL_DECLARATION],
                "preview": True,
            },
            "unit",
        ),
    )
    for index, (request, reason) in enumerate(cases):
        target = tmp_path / str(index)
        target.mkdir()
        marker = target / "marker.bin"
        marker.write_bytes(b"unchanged")
        before = _tree_snapshot(target)

        result = InitScaffoldTool().execute(
            path=str(target),
            **EXPERIMENT_IDENTITY,
            **request,
        )

        assert result.success is False
        assert reason in (result.error or "").lower()
        assert _tree_snapshot(target) == before


ACTION_ONLY_PROTOCOL: dict[str, object] = {
    "action": "create",
    "contracts": [{"name": "brief"}],
    "prompts": [{"name": "author", "text": "Author the work."}],
    "nodes": [{"name": "author", "contract": "brief", "prompt": "author"}],
    "phases": [{"name": "draft", "nodes": ["author"]}],
    "ticket": {"ticket_type": "dev.work", "input_contract": "brief"},
}


def _write_protocol_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        # The target owns the profile up front: a unit/protocol request
        # refuses a package that declares none rather than registering one.
        '[project]\nname = "protocols-dev"\nversion = "0.1.0"\n'
        '\n[tool.axm-init.protocols]\nschema_version = 1\ndomain = "dev"\n',
        encoding="utf-8",
    )


@pytest.mark.integration
def test_protocol_unit_mode_previews_action_only_protocol(tmp_path: Path) -> None:
    """AC1: protocol_unit reaches structured preview with request identity."""
    _write_protocol_project(tmp_path)

    result = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="protocol_unit",
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[ACTION_ONLY_PROTOCOL],
        preview=True,
        **EXPERIMENT_IDENTITY,
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["preview"] is True


@pytest.mark.integration
@pytest.mark.integration
def test_protocol_mode_without_preview_applies_only_its_plan(tmp_path: Path) -> None:
    """AC1: non-preview protocol mode writes its plan and no project template."""
    _write_protocol_project(tmp_path)
    preview = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="protocol",
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[ACTION_ONLY_PROTOCOL],
        preview=True,
        **EXPERIMENT_IDENTITY,
    )
    assert preview.success is True, preview.error
    assert preview.data is not None
    planned = set(preview.data["created"])

    applied = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="protocol",
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[ACTION_ONLY_PROTOCOL],
        preview=False,
        **EXPERIMENT_IDENTITY,
    )

    assert applied.success is True, applied.error
    assert applied.data is not None
    assert set(applied.data["created"]) == planned
    landed = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert landed == planned | {"pyproject.toml"}
    assert landed.isdisjoint(
        {
            "LICENSE",
            "CONTRIBUTING.md",
            "mkdocs.yml",
            ".github/workflows/ci.yml",
        }
    )


def test_protocol_mode_previews_action_only_protocol_in_existing_unit(
    tmp_path: Path,
) -> None:
    """AC2: protocol reaches structured preview for an existing unit."""
    _write_protocol_project(tmp_path)
    (tmp_path / "src" / "protocols_dev" / "work").mkdir(parents=True)

    result = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="protocol",
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[ACTION_ONLY_PROTOCOL],
        preview=True,
        **EXPERIMENT_IDENTITY,
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["preview"] is True


@pytest.mark.integration
def test_public_workspace_member_omits_private_classifier(tmp_path: Path) -> None:
    """AC1: private=False rend le membre public avec ses classifiers ordonnés."""
    workspace_root = tmp_path / "workspace"
    workspace = _scaffold_without_tasks(
        workspace_root,
        name="public-workspace",
        workspace=True,
    )
    assert workspace.success is True, workspace.error

    member = _scaffold_without_tasks(
        workspace_root,
        member="public-member",
        private=False,
    )

    assert member.success is True, member.error
    pyproject = workspace_root / "packages" / "public-member" / "pyproject.toml"
    rendered = pyproject.read_text(encoding="utf-8")
    project = tomllib.loads(rendered)["project"]
    assert "Private :: Do Not Upload" not in rendered
    assert project["classifiers"] == [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ]


@pytest.mark.integration
def test_public_standalone_project_omits_private_classifier(tmp_path: Path) -> None:
    """AC2: private=False rend le projet public avec ses classifiers ordonnés."""
    project_root = tmp_path / "public-project"

    result = _scaffold_without_tasks(
        project_root,
        name="public-project",
        private=False,
    )

    assert result.success is True, result.error
    pyproject = project_root / "pyproject.toml"
    rendered = pyproject.read_text(encoding="utf-8")
    project = tomllib.loads(rendered)["project"]
    assert "Private :: Do Not Upload" not in rendered
    assert project["classifiers"] == [
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Typing :: Typed",
        "License :: OSI Approved :: Apache Software License",
    ]


def _scaffold_learning(tmp_path: Path) -> tuple[Path, ToolResult]:
    target = tmp_path / "learning-lab"
    result = _scaffold_without_tasks(
        target,
        name="learning-lab",
        kind="learning",
    )
    return target, result


@pytest.mark.integration
def test_learning_scaffold_reports_template_profile_and_mode(tmp_path: Path) -> None:
    """AC3: standalone learning reports its template, profile and mode."""
    _target, result = _scaffold_learning(tmp_path)

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["template"] == "learning"
    assert result.data["profile"] == "learning"
    assert result.data["mode"] == "standalone"


@pytest.mark.integration
def test_learning_scaffold_writes_learning_artifacts(tmp_path: Path) -> None:
    """AC4: the learning scaffold renders every required training artefact."""
    target, result = _scaffold_learning(tmp_path)

    assert result.success is True, result.error
    expected = {
        "pyproject.toml",
        "training.toml",
        "study.toml",
        "src/learning_lab/learning/recipe.py",
        "src/learning_lab/learning/tool.py",
        "tests_learning_lab/unit/test_recipe.py",
    }
    missing = sorted(path for path in expected if not (target / path).is_file())
    assert missing == []


@pytest.mark.integration
def test_learning_pyproject_declares_nonempty_domain(tmp_path: Path) -> None:
    """AC5: generated metadata declares a non-empty learning domain."""
    target, result = _scaffold_learning(tmp_path)
    assert result.success is True, result.error

    metadata = tomllib.loads((target / "pyproject.toml").read_text(encoding="utf-8"))
    profile = metadata["tool"]["axm-init"]["learning"]
    assert isinstance(profile["domain"], str)
    assert profile["domain"].strip()


@pytest.mark.integration
def test_learning_pyproject_declares_training_tool_entry_point(
    tmp_path: Path,
) -> None:
    """AC6: generated metadata exposes the rendered training AXMTool."""
    target, result = _scaffold_learning(tmp_path)
    assert result.success is True, result.error

    metadata = tomllib.loads((target / "pyproject.toml").read_text(encoding="utf-8"))
    entry_points = metadata["project"]["entry-points"]["axm.tools"]
    targets = [str(value).split(":", 1)[0] for value in entry_points.values()]
    assert "learning_lab.learning.tool" in targets


@pytest.mark.integration
def test_learning_rerun_preserves_edited_recipe_bytes(tmp_path: Path) -> None:
    """AC1: an identical learning re-run preserves user-owned recipe bytes."""
    target, initial = _scaffold_learning(tmp_path)
    assert initial.success is True, initial.error
    recipe = target / "src" / "learning_lab" / "learning" / "recipe.py"
    edited = recipe.read_bytes() + b"\n# user-owned marker\n"
    recipe.write_bytes(edited)

    rerun = _scaffold_without_tasks(
        target,
        name="learning-lab",
        kind="learning",
    )

    assert rerun.success is True, rerun.error
    assert recipe.read_bytes() == edited


@pytest.mark.integration
def test_learning_rerun_refreshes_training_configuration(tmp_path: Path) -> None:
    """AC2: the identical re-run refreshes template-owned training config."""
    target, initial = _scaffold_learning(tmp_path)
    assert initial.success is True, initial.error
    training = target / "training.toml"
    marker = "hand_written_marker = true"
    training.write_text(f"{marker}\n", encoding="utf-8")

    rerun = _scaffold_without_tasks(
        target,
        name="learning-lab",
        kind="learning",
    )

    assert rerun.success is True, rerun.error
    refreshed = training.read_text(encoding="utf-8")
    assert marker not in refreshed
    assert 'entry_point = "learning_lab.learning.recipe:SyntheticRecipe"' in refreshed


@pytest.mark.integration
def test_learning_member_rerun_reconciles_same_domain_and_preserves_recipe(
    tmp_path: Path,
) -> None:
    """AC1: a same-domain member re-run succeeds and preserves recipe bytes."""
    workspace_root = tmp_path / "workspace"
    workspace = _scaffold_without_tasks(
        workspace_root,
        name="learning-workspace",
        workspace=True,
    )
    assert workspace.success is True, workspace.error
    initial = _scaffold_without_tasks(
        workspace_root,
        member="learning-member",
        kind="learning",
        domain="forecasting",
    )
    assert initial.success is True, initial.error
    member_root = workspace_root / "packages" / "learning-member"
    recipe = member_root / "src" / "learning_member" / "recipe.py"
    edited = recipe.read_bytes() + b"\n# user-owned member marker\n"
    recipe.write_bytes(edited)

    rerun = _scaffold_without_tasks(
        workspace_root,
        member="learning-member",
        kind="learning",
        domain="forecasting",
    )

    assert rerun.success is True, rerun.error
    assert recipe.read_bytes() == edited


@pytest.mark.integration
def test_learning_member_domain_conflict_is_atomic_and_names_both_domains(
    tmp_path: Path,
) -> None:
    """AC2: a changed-domain member re-run names both domains and writes nothing."""
    workspace_root = tmp_path / "workspace"
    workspace = _scaffold_without_tasks(
        workspace_root,
        name="learning-workspace",
        workspace=True,
    )
    assert workspace.success is True, workspace.error
    initial = _scaffold_without_tasks(
        workspace_root,
        member="learning-member",
        kind="learning",
        domain="forecasting",
    )
    assert initial.success is True, initial.error
    member_root = workspace_root / "packages" / "learning-member"
    recipe = member_root / "src" / "learning_member" / "recipe.py"
    training = member_root / "training.toml"
    recipe.write_bytes(recipe.read_bytes() + b"\n# user-owned member marker\n")
    recipe_before = recipe.read_bytes()
    training_before = training.read_bytes()

    conflict = _scaffold_without_tasks(
        workspace_root,
        member="learning-member",
        kind="learning",
        domain="ranking",
    )

    assert conflict.success is False
    error = conflict.error or ""
    assert "forecasting" in error
    assert "ranking" in error
    assert "profile is required for a protocol package" not in error
    assert recipe.read_bytes() == recipe_before
    assert training.read_bytes() == training_before
