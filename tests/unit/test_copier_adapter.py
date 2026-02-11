"""Tests for Copier adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from axm_init.adapters.copier import CopierAdapter, CopierConfig


class TestCopierConfig:
    """Tests for CopierConfig model."""

    def test_config_requires_template_path(self, tmp_path: Path) -> None:
        """Test that template_path is required."""
        with pytest.raises(ValidationError):
            CopierConfig(destination=tmp_path, data={})  # type: ignore[call-arg]

    def test_config_has_defaults(self, tmp_path: Path) -> None:
        """Test default values are set."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "project",
            data={"package_name": "test"},
        )
        assert config.defaults is True
        assert config.overwrite is False


class TestCopierAdapter:
    """Tests for CopierAdapter."""

    def test_copy_returns_scaffold_result(self, tmp_path: Path) -> None:
        """Test that copy returns ScaffoldResult."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "test-project",
            data={"package_name": "test"},
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.return_value = MagicMock()
            result = adapter.copy(config)

        assert result.success is True
        assert "test-project" in result.path

    def test_copy_passes_data_to_copier(self, tmp_path: Path) -> None:
        """Test that data dict is passed to Copier."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "my-pkg",
            data={"package_name": "my-pkg", "description": "A test package"},
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["data"] == {
            "package_name": "my-pkg",
            "description": "A test package",
        }

    def test_copy_handles_copier_error(self, tmp_path: Path) -> None:
        """Test graceful handling of Copier errors."""
        config = CopierConfig(
            template_path=Path("/nonexistent/template"),
            destination=tmp_path / "will-fail",
            data={},
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.side_effect = RuntimeError("Template not found")
            result = adapter.copy(config)

        assert result.success is False
        assert "Template not found" in result.message
