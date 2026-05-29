"""Unit tests for reserver (pure logic, no I/O)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from axm_init.core.reserver import build_package, publish_package, reserve_pypi
from axm_init.models.results import AvailabilityStatus


class TestReserveResult:
    """Tests for ReserveResult model."""

    def test_reserve_result_success(self) -> None:
        """ReserveResult captures success state."""
        from axm_init.models.results import ReserveResult

        result = ReserveResult(
            success=True,
            package_name="my-package",
            version="0.0.1.dev0",
            message="Published successfully",
        )
        assert result.success is True
        assert result.package_name == "my-package"

    def test_reserve_result_model_dump(self) -> None:
        """ReserveResult supports Pydantic model_dump()."""
        from axm_init.models.results import ReserveResult

        result = ReserveResult(
            success=True,
            package_name="my-pkg",
            version="0.0.1.dev0",
            message="ok",
        )
        data = result.model_dump()
        assert data == {
            "success": True,
            "package_name": "my-pkg",
            "version": "0.0.1.dev0",
            "message": "ok",
        }

    def test_reserve_result_extra_forbidden(self) -> None:
        """ReserveResult rejects unknown fields."""
        from axm_init.models.results import ReserveResult

        with pytest.raises(ValidationError, match="extra"):
            ReserveResult(
                success=True,
                package_name="pkg",
                version="0.0.1",
                message="ok",
                typo_field="should fail",  # type: ignore[call-arg]
            )


class TestReserverUnit:
    """Unit tests for PyPI reservation (no I/O, mocked subprocess/adapter)."""

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    def test_reserve_race_condition(
        self,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Race condition: recheck returns TAKEN → success=False."""
        checker = MagicMock()
        # First check: AVAILABLE, recheck after "already exists": TAKEN
        checker.check_availability.side_effect = [
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.TAKEN,
        ]
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi(
            name="race-pkg",
            author="Test",
            email="test@example.com",
            token="pypi-test",
            checker=checker,
        )

        assert result.success is False
        assert "taken by another user" in result.message.lower()

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    def test_reserve_idempotent_rerun(
        self,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Idempotent re-run: recheck returns AVAILABLE → success=True."""
        checker = MagicMock()
        # First check: AVAILABLE, recheck after "already exists": AVAILABLE
        checker.check_availability.side_effect = [
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.AVAILABLE,
        ]
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi(
            name="idem-pkg",
            author="Test",
            email="test@example.com",
            token="pypi-test",
            checker=checker,
        )

        assert result.success is True
        assert "already reserved" in result.message.lower()

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    def test_reserve_recheck_error_fails_safe(
        self,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Network error on recheck → fail-safe (success=True, idempotent)."""
        checker = MagicMock()
        # First check: AVAILABLE, recheck after "already exists": ERROR
        checker.check_availability.side_effect = [
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.ERROR,
        ]
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi(
            name="err-pkg",
            author="Test",
            email="test@example.com",
            token="pypi-test",
            checker=checker,
        )

        # ERROR on recheck = can't confirm race, assume idempotent
        assert result.success is True
        assert "already reserved" in result.message.lower()


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

    @patch("axm_init.core.reserver.subprocess.run")
    def test_publish_uses_env_not_cli_arg(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Token must be passed via UV_PUBLISH_TOKEN env var, not --token CLI arg."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "publish"], returncode=0, stdout="", stderr=""
        )
        publish_package(tmp_path, "pypi-secret-token-123")

        call_args = mock_run.call_args
        cmd = call_args.args[0] if call_args.args else call_args.kwargs.get("args", [])
        # --token must NOT appear in the command line
        assert "--token" not in cmd
        assert "pypi-secret-token-123" not in cmd
        # Token must be in the environment variable
        env = call_args.kwargs.get("env", {})
        assert env["UV_PUBLISH_TOKEN"] == "pypi-secret-token-123"

    @patch("axm_init.core.reserver.subprocess.run")
    def test_publish_empty_token(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Empty token is still passed via env var — uv handles the error."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "publish"], returncode=0, stdout="", stderr=""
        )
        publish_package(tmp_path, "")

        env = mock_run.call_args.kwargs.get("env", {})
        assert env["UV_PUBLISH_TOKEN"] == ""

    @patch("axm_init.core.reserver.subprocess.run")
    def test_publish_token_special_chars(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Token with special chars ($, !, spaces) passes safely via env."""
        special_token = "pypi-$ecret! with spaces"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "publish"], returncode=0, stdout="", stderr=""
        )
        publish_package(tmp_path, special_token)

        env = mock_run.call_args.kwargs.get("env", {})
        assert env["UV_PUBLISH_TOKEN"] == special_token


class TestReservePyPIFlow:
    """Tests for reserve_pypi() full flow — build + publish paths."""

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    def test_full_reserve_success(
        self,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Full reserve flow: available → build → publish → success."""
        checker = MagicMock()
        checker.check_availability.return_value = AvailabilityStatus.AVAILABLE
        mock_build.return_value = (True, "")
        mock_publish.return_value = (True, "")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is True
        assert "Reserved" in result.message

    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    def test_reserve_build_fails(
        self,
        mock_create: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """Build failure returns error result."""
        checker = MagicMock()
        checker.check_availability.return_value = AvailabilityStatus.AVAILABLE
        mock_build.return_value = (False, "compile error")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is False
        assert "Build failed" in result.message

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    def test_reserve_race_condition(
        self,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Race condition: name taken between check and publish → failure."""
        checker = MagicMock()
        # First call: AVAILABLE (initial check), second call: TAKEN (re-check)
        checker.check_availability.side_effect = [
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.TAKEN,
        ]
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is False
        assert "taken by another user" in result.message.lower()

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    def test_reserve_idempotent_rerun(
        self,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Idempotent re-run: our own prior reservation → success."""
        checker = MagicMock()
        checker.check_availability.side_effect = [
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.AVAILABLE,
        ]
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "File already exists")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is True
        assert "already reserved" in result.message.lower()

    @patch("axm_init.core.reserver.publish_package")
    @patch("axm_init.core.reserver.build_package")
    @patch("axm_init.core.reserver.create_minimal_package")
    def test_reserve_publish_fails(
        self,
        mock_create: MagicMock,
        mock_build: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Generic publish failure returns error result."""
        checker = MagicMock()
        checker.check_availability.return_value = AvailabilityStatus.AVAILABLE
        mock_build.return_value = (True, "")
        mock_publish.return_value = (False, "network timeout")

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is False
        assert "Publish failed" in result.message

    def test_reserve_availability_error(self) -> None:
        """Availability check error returns error result."""
        checker = MagicMock()
        checker.check_availability.return_value = AvailabilityStatus.ERROR

        result = reserve_pypi("new-pkg", "Author", "a@b.com", "token", checker=checker)
        assert result.success is False
        assert "availability" in result.message.lower()
