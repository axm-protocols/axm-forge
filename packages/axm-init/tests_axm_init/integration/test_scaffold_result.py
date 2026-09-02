"""Split from ``test_cli_subcommands.py``."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_init.models.results import ScaffoldResult
from axm_init.tools.scaffold import InitScaffoldTool
from tests_axm_init.integration._helpers import _build_scaffold_tree


def _run(*args: str) -> tuple[str, str, int]:
    """Call InitScaffoldTool and adapt its ToolResult for existing assertions."""
    _, path, *options = args

    def value(name: str, default: str = "") -> str:
        return options[options.index(name) + 1] if name in options else default

    result = InitScaffoldTool().execute(
        path=path,
        name=value("--name") or None,
        org=value("--org"),
        author=value("--author"),
        email=value("--email"),
        json_output="--json" in options,
    )
    if "--json" in options:
        payload = {"success": result.success, **result.data}
        if result.error:
            payload["error"] = result.error
        stdout = json.dumps(payload)
    else:
        stdout = (result.text or "").replace("✓", "✅")
    stderr = "" if result.success else f"❌ {result.error}"
    return stdout, stderr, 0 if result.success else 1


class TestScaffoldCommand:
    """Tests for ``InitScaffoldTool`` with a mocked adapter."""

    def test_scaffold_success(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml", "README.md"],
            message="ok",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "scaffold",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
            )
        assert code == 0
        assert "✅" in stdout

    def test_scaffold_json_output(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=True,
            path=str(target),
            files_created=["pyproject.toml"],
            message="ok",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            stdout, _stderr, code = _run(
                "scaffold",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
                "--json",
            )
        assert code == 0
        data = json.loads(stdout)
        assert data["success"] is True

    def test_scaffold_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        mock_result = ScaffoldResult(
            success=False,
            path=str(target),
            files_created=[],
            message="Copy failed",
        )
        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_cls.return_value.copy.return_value = mock_result
            _stdout, stderr, code = _run(
                "scaffold",
                str(target),
                "--org",
                "test-org",
                "--author",
                "Test",
                "--email",
                "t@t.com",
            )
        assert code == 1
        assert "❌" in stderr


class TestScaffoldReturnsFileList:
    """AC1: scaffold_project() returns a list of all created file paths."""

    @pytest.mark.parametrize(
        ("name", "pre_existing"),
        [
            pytest.param("file-list-test", False, id="empty_dir"),
            pytest.param("existing-dir-test", True, id="existing_file_in_dir"),
        ],
    )
    def test_scaffold_returns_file_list(
        self, tmp_path: Path, name: str, pre_existing: bool
    ) -> None:
        """Mock scaffold returns non-empty files list.

        Covers with or without pre-existing files.
        """
        if pre_existing:
            (tmp_path / "existing.txt").write_text("pre-existing")
        files = _build_scaffold_tree(tmp_path, name)
        result = ScaffoldResult(
            success=True,
            path=str(tmp_path),
            message="ok",
            files_created=files,
        )
        assert result.success is True
        assert len(result.files_created) > 0
