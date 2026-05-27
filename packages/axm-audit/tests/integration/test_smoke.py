"""Integration tests for axm_audit.core.fix end-to-end smoke on empty packages."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_run_on_empty_package_returns_empty_plan(tmp_path: Path) -> None:
    """AC2: pipeline on a package with only an empty tests/ dir yields no ops."""
    from axm_audit.core.fix import run

    (tmp_path / "tests").mkdir()

    report = run(tmp_path)

    assert report.ops == []
    assert report.applied is False
