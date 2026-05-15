"""Unit tests for Copier adapter (pure mock, no real I/O)."""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
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

    def test_copier_unsafe_defaults_false(self, tmp_path: Path) -> None:
        """trust_template defaults to False."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "project",
            data={"package_name": "test"},
        )
        assert config.trust_template is False


class TestCopierAdapterUnit:
    """Pure call-wiring tests for CopierAdapter (mock-only, no real I/O)."""

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

    @pytest.mark.parametrize(
        ("trust", "expected_unsafe", "dest_name"),
        [
            pytest.param(False, False, "untrusted", id="trust_false_unsafe_false"),
            pytest.param(True, True, "trusted", id="trust_true_unsafe_true"),
        ],
    )
    def test_copier_copy_propagates_trust_flag(
        self, tmp_path: Path, trust: bool, expected_unsafe: bool, dest_name: str
    ) -> None:
        """trust_template propagates to run_copy's unsafe kwarg."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / dest_name,
            data={"package_name": "test"},
            trust_template=trust,
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        assert mock_run.call_args.kwargs["unsafe"] is expected_unsafe

    def test_copier_copy_warns_when_unsafe(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is logged when trust_template=True."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "warn-test",
            data={"package_name": "test"},
            trust_template=True,
        )
        adapter = CopierAdapter()

        with (
            patch("axm_init.adapters.copier.run_copy") as mock_run,
            caplog.at_level(logging.WARNING, logger="axm_init.adapters.copier"),
        ):
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        assert any("unsafe=True" in r.message for r in caplog.records)

    def test_copier_copy_no_warning_when_safe(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning is logged when trust_template=False."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "safe-test",
            data={"package_name": "test"},
            trust_template=False,
        )
        adapter = CopierAdapter()

        with (
            patch("axm_init.adapters.copier.run_copy") as mock_run,
            caplog.at_level(logging.WARNING, logger="axm_init.adapters.copier"),
        ):
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        assert not any("unsafe" in r.message.lower() for r in caplog.records)


def test_copier_imports_at_runtime() -> None:
    """Importing copier adapter in a fresh interpreter raises no ImportError."""
    code = textwrap.dedent("""
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        print("OK")
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ImportError: {result.stderr}"
    assert "OK" in result.stdout


def test_copier_adapter_instantiation() -> None:
    """CopierAdapter can be instantiated after import refactor."""
    from axm_init.adapters.copier import CopierAdapter

    adapter = CopierAdapter()
    assert hasattr(adapter, "copy")
    assert hasattr(adapter, "_do_copy")
