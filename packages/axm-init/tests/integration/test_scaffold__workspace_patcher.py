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
