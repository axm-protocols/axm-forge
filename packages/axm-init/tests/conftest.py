"""Shared test fixtures for axm-init tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_init.adapters.copier import CopierConfig
from axm_init.models.results import ScaffoldResult

# ── Sample Data ──────────────────────────────────────────────────────────

SAMPLE_PROJECT_NAME = "test-project"
SAMPLE_AUTHOR = "Test Author"
SAMPLE_EMAIL = "test@example.com"
SAMPLE_DESCRIPTION = "A test project"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A temporary directory for project scaffolding."""
    target = tmp_path / "my-project"
    target.mkdir()
    return target


@pytest.fixture
def sample_copier_config(project_dir: Path) -> CopierConfig:
    """A fully populated CopierConfig for testing."""
    return CopierConfig(
        template_path=Path("src/axm_init/templates/python-project"),
        destination=project_dir,
        data={
            "package_name": SAMPLE_PROJECT_NAME,
            "description": SAMPLE_DESCRIPTION,
            "org": "TestOrg",
            "license": "MIT",
            "author_name": SAMPLE_AUTHOR,
            "author_email": SAMPLE_EMAIL,
        },
    )


@pytest.fixture
def sample_scaffold_result() -> ScaffoldResult:
    """A successful ScaffoldResult."""
    return ScaffoldResult(
        success=True,
        path="test-project",
        message="Project scaffolded via Copier",
    )


@pytest.fixture
def failed_scaffold_result() -> ScaffoldResult:
    """A failed ScaffoldResult."""
    return ScaffoldResult(
        success=False,
        path="test-project",
        message="Copier failed: template not found",
    )


@pytest.fixture
def mock_pypi_adapter() -> MagicMock:
    """A mock PyPIAdapter."""
    return MagicMock()
