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
