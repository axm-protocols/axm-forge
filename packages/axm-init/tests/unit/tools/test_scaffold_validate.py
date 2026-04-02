from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_init.tools.scaffold import InitScaffoldTool


class TestExtractedValidateInputs:
    """Tests for the extracted input validation helper."""

    def test_missing_org_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="a", email="e@x.com", org="")
        assert not result.success
        assert result.error is not None
        assert "org" in result.error.lower() or "required" in result.error.lower()

    def test_missing_author_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="", email="e@x.com", org="myorg")
        assert not result.success
        assert result.error is not None
        assert "required" in result.error.lower()

    def test_missing_email_returns_error(self) -> None:
        tool = InitScaffoldTool()
        result = tool.execute(path=".", author="a", email="", org="myorg")
        assert not result.success
        assert result.error is not None
        assert "required" in result.error.lower()

    def test_valid_inputs_no_validation_error(
        self, tmp_path: Path, mocker: Any
    ) -> None:
        """Valid inputs should pass validation and reach scaffold logic."""
        # Mock copier to avoid filesystem side effects
        mock_copy = mocker.patch(
            "axm_init.adapters.copier.CopierAdapter.copy",
        )
        mock_copy.return_value = mocker.MagicMock(
            success=True,
            files_created=[],
            message="",
        )
        mocker.patch(
            "axm_init.core.templates.get_template_path",
            return_value=str(tmp_path),
        )
        tool = InitScaffoldTool()
        result = tool.execute(
            path=str(tmp_path),
            author="Author",
            email="a@b.com",
            org="myorg",
        )
        # Should not fail on validation — may fail downstream but not with 'required'
        if not result.success:
            assert result.error is not None
            assert "required" not in result.error.lower()
