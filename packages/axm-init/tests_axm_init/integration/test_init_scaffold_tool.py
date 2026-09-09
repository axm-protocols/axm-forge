"""Split from ``test_scaffold_tool_error_paths_and_member.py``."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_init.tools.scaffold import InitScaffoldTool


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


def _scaffold_paper_then_experiment(tmp_path: Path) -> Any:
    # Render a real paper, then a real experiment inside it (no mocks).
    tool = InitScaffoldTool()
    paper = tool.execute(path=str(tmp_path), kind="paper", **EXPERIMENT_IDENTITY)
    assert paper.success is True, paper.error
    experiment = tool.execute(
        path=str(tmp_path), kind="experiment", **EXPERIMENT_IDENTITY
    )
    assert experiment.success is True, experiment.error
    return experiment


def _rendered_files(experiment_dir: Path) -> set[str]:
    # Every file actually written under the produced experiment directory.
    return {
        p.relative_to(experiment_dir).as_posix()
        for p in experiment_dir.rglob("*")
        if p.is_file()
    }


@pytest.mark.integration
class TestExperimentManifestContract:
    # The experiment scaffold reports the manifest.yaml contract file, named
    # exactly as it lands inside the experiment directory it reports.

    def test_reported_files_name_manifest_inside_the_produced_tree(
        self, tmp_path: Path
    ) -> None:
        """AC1: the reported list names manifest.yaml, never experiment.yaml.

        The reported names are the files the template rendered into the
        reported experiment directory, so each one must resolve there.
        """
        experiment = _scaffold_paper_then_experiment(tmp_path)

        assert experiment.data is not None
        files = [str(f) for f in experiment.data["files"]]
        experiment_dir = Path(str(experiment.data["path"]))
        assert any(Path(f).name == "manifest.yaml" for f in files), files
        assert not any(Path(f).name == "experiment.yaml" for f in files), files
        unresolved = [f for f in files if not (experiment_dir / f).is_file()]
        assert unresolved == []

    def test_scaffolded_tree_holds_manifest_and_matches_the_report(
        self, tmp_path: Path
    ) -> None:
        """AC2: manifest.yaml sits at the experiment root, no experiment.yaml.

        The tool's reported file list and the tree on disk must agree — the
        report is exactly the set of files rendered under the experiment root.
        """
        experiment = _scaffold_paper_then_experiment(tmp_path)

        assert experiment.data is not None
        experiment_dir = Path(str(experiment.data["path"]))
        assert (experiment_dir / "manifest.yaml").is_file()
        assert list(tmp_path.rglob("experiment.yaml")) == []
        reported = {str(f) for f in experiment.data["files"]}
        assert reported == _rendered_files(experiment_dir)


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


@pytest.mark.integration
def test_python_package_and_member_register_protocol_profile(tmp_path: Path) -> None:
    """AC1: both Python modes expose their derived distribution and location."""
    tool = InitScaffoldTool()
    package_root = tmp_path / "protocols-dev"
    package = tool.execute(
        path=str(package_root),
        name="protocols-dev",
        profile="protocols",
        domain="dev",
        protocols=[],
        **EXPERIMENT_IDENTITY,
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
    workspace = tool.execute(
        path=str(workspace_root),
        name="protocol-workspace",
        workspace=True,
        **EXPERIMENT_IDENTITY,
    )
    assert workspace.success, workspace.error
    member = tool.execute(
        path=str(workspace_root),
        member="protocols-research",
        profile="protocols",
        domain="research",
        protocols=[],
        **EXPERIMENT_IDENTITY,
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
