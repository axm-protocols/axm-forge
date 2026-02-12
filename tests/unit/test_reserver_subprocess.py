"""Tests for reserver.py subprocess paths — build, publish, reserve flow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_init.adapters.pypi import AvailabilityStatus
from axm_init.core.reserver import (
    build_package,
    publish_package,
    reserve_pypi,
)


class TestBuildPackage:
    """Tests for build_package()."""

    @patch("axm_init.core.reserver.subprocess.run")
    def test_build_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """build_package returns (True, '') on success."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "build"], returncode=0, stdout="", stderr=""
        )
        ok, err = build_package(tmp_path)
        assert ok is True
        assert err == ""

    @patch("axm_init.core.reserver.subprocess.run")
    def test_build_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """build_package returns (False, stderr) on failure."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "build"], returncode=1, stdout="", stderr="build error"
        )
        ok, err = build_package(tmp_path)
        assert ok is False
        assert "build error" in err


class TestPublishPackage:
    """Tests for publish_package()."""

    @patch("axm_init.core.reserver.subprocess.run")
    def test_publish_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """publish_package returns (True, '') on success."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "publish"], returncode=0, stdout="", stderr=""
        )
        ok, err = publish_package(tmp_path, "pypi-token")
        assert ok is True
        assert err == ""

    @patch("axm_init.core.reserver.subprocess.run")
    def test_publish_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """publish_package returns (False, stderr) on failure."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "publish"], returncode=1, stdout="", stderr="auth error"
        )
        ok, err = publish_package(tmp_path, "pypi-token")
        assert ok is False
        assert "auth error" in err


class TestReservePyPIFlow:
    """Tests for reserve_pypi() full flow — build + publish paths."""

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    @patch("axm_init.core.reserver.PyPIAdapter")
    def test_full_reserve_success(
        self,
        mock_pypi: MagicMock,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Full reserve flow: available → build → publish → success."""
        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.AVAILABLE
        )
        mock_build.return_value = (True, "")
        mock_publish.return_value = (True, "")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token")
        assert result.success is True
        assert "Reserved" in result.message

    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    @patch("axm_init.core.reserver.PyPIAdapter")
    def test_reserve_build_fails(
        self,
        mock_pypi: MagicMock,
        mock_create: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """Build failure returns error result."""
        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.AVAILABLE
        )
        mock_build.return_value = (False, "compile error")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token")
        assert result.success is False
        assert "Build failed" in result.message

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    @patch("axm_init.core.reserver.PyPIAdapter")
    def test_reserve_publish_already_exists(
        self,
        mock_pypi: MagicMock,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Publish 'already exists' error is treated as success."""
        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.AVAILABLE
        )
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token")
        assert result.success is True
        assert "already reserved" in result.message.lower()

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    @patch("axm_init.core.reserver.PyPIAdapter")
    def test_reserve_publish_fails(
        self,
        mock_pypi: MagicMock,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Generic publish failure returns error result."""
        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.AVAILABLE
        )
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "network timeout")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token")
        assert result.success is False
        assert "Publish failed" in result.message

    @patch("axm_init.core.reserver.PyPIAdapter")
    def test_reserve_availability_error(self, mock_pypi: MagicMock) -> None:
        """Availability check error returns error result."""
        mock_pypi.return_value.check_availability.return_value = (
            AvailabilityStatus.ERROR
        )

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token")
        assert result.success is False
        assert "availability" in result.message.lower()
