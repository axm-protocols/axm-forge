"""tools.scaffold + patch_all: patched_root_files excludes skipped files."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestScaffoldMemberReportsTruthfulPatches:
    """AC2: the scaffold CLI never lists a skipped file as patched."""

    def test_patched_root_files_excludes_skipped(
        self, workspace_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from axm_init.cli import scaffold

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files_created = [Path("pyproject.toml")]
        mock_result.message = ""

        with patch("axm_init.adapters.copier.CopierAdapter") as mock_cls:
            mock_copier = MagicMock()
            mock_copier.copy.return_value = mock_result
            mock_cls.return_value = mock_copier

            scaffold(
                str(workspace_root),
                org="test-org",
                author="Test",
                email="test@test.com",
                member="my-lib",
                json_output=True,
            )

        payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        # release.yml is absent from the fixture → surfaced as skipped, not patched.
        assert ".github/workflows/release.yml" in payload["skipped_root_files"]
        assert ".github/workflows/release.yml" not in payload["patched_root_files"]
        # patched and skipped never overlap.
        overlap = set(payload["patched_root_files"]) & set(
            payload["skipped_root_files"]
        )
        assert overlap == set()


def test_member_scaffold_patches_correct_blocks_with_decoys(tmp_path: Path) -> None:
    """AC3: decoy ``jobs:`` comment + ``testpaths_extra`` are never mis-patched."""
    from axm_init.adapters.workspace_patcher import patch_publish, patch_testpaths

    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "publish.yml").write_text(
        "name: Publish\n\n"
        'on:\n  push:\n    tags:\n      - "existing/v*"\n\n'
        "# jobs: decoy\n"
        "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n\n'
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths_extra = ["packages/decoy/tests"]\n'
        'testpaths = [\n    "packages/existing/tests",\n]\n'
    )

    assert patch_publish(tmp_path, "my-lib") is True
    assert patch_testpaths(tmp_path, "my-lib") is True

    publish = (wf / "publish.yml").read_text()
    pyproject = (tmp_path / "pyproject.toml").read_text()

    # publish.yml: tag added to the real tags block, decoy comment intact.
    assert '"my-lib/v*"' in publish
    assert "# jobs: decoy" in publish
    # pyproject: new testpath in testpaths, testpaths_extra decoy untouched.
    assert '"packages/my-lib/tests_my_lib"' in pyproject
    assert 'testpaths_extra = ["packages/decoy/tests"]' in pyproject
    assert '"packages/existing/tests"' in pyproject
