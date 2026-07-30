"""Unit tests for axm_audit.hooks.quality_check."""

from __future__ import annotations

import pytest

from axm_audit.hooks.quality_check import QualityCheckHook


@pytest.fixture
def hook() -> QualityCheckHook:
    return QualityCheckHook()


class TestUnitScope:
    def test_invalid_working_dir(self, hook: QualityCheckHook) -> None:
        context = {"working_dir": "/nonexistent/path/that/does/not/exist"}

        result = hook.execute(context)

        assert result.metadata["has_violations"] is False
