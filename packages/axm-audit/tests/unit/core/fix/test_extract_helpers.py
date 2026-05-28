"""Unit tests for axm_audit.core.fix.extract_helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import (
    _extract_shared_helpers,
    _extract_shared_helpers_in_tier,
    _extract_shared_helpers_once,
    _load_or_create_conftest_module,
    _load_or_create_helpers_module,
)

# A path tree guaranteed not to exist on disk. Every code path exercised below
# keys on ``Path.is_dir()`` / ``Path.exists()`` returning ``False`` and never
# reaches ``read_text`` / ``cst_save``, so no real I/O is performed (keeps these
# tests at the unit pyramid level).
_ABSENT_ROOT = Path("/nonexistent-axm-audit-extract-root")


def test_extract_shared_helpers_once_returns_empty_without_tests_dir() -> None:
    """_extract_shared_helpers_once yields no messages when tests/ is absent."""
    assert _extract_shared_helpers_once(_ABSENT_ROOT) == []


def test_extract_shared_helpers_returns_empty_without_tests_dir() -> None:
    """_extract_shared_helpers reaches fixed-point immediately on an empty project."""
    assert _extract_shared_helpers(_ABSENT_ROOT) == []


def test_extract_shared_helpers_in_tier_returns_empty_for_absent_tier() -> None:
    """_extract_shared_helpers_in_tier yields nothing when the tier dir is empty."""
    tier = _ABSENT_ROOT / "tests" / "integration"
    assert _extract_shared_helpers_in_tier(_ABSENT_ROOT, tier) == []


def test_load_or_create_helpers_module_synthesizes_when_absent() -> None:
    """_load_or_create_helpers_module parses a fresh stub module for a missing path."""
    module = _load_or_create_helpers_module(
        _ABSENT_ROOT / "tests" / "unit" / "_helpers.py",
        "unit",
        "tests.unit._helpers",
    )
    assert module is not None


def test_load_or_create_helpers_module_embeds_tier_and_module_path() -> None:
    """The synthesized helpers stub names the tier and the import module path."""
    module = _load_or_create_helpers_module(
        _ABSENT_ROOT / "tests" / "e2e" / "_helpers.py",
        "e2e",
        "tests.e2e._helpers",
    )
    assert module is not None
    code = module.code
    assert "tests/e2e" in code
    assert "from tests.e2e._helpers import <name>" in code


def test_load_or_create_helpers_module_includes_future_import() -> None:
    """The synthesized helpers stub carries the mandatory future-annotations import."""
    module = _load_or_create_helpers_module(
        _ABSENT_ROOT / "tests" / "unit" / "_helpers.py",
        "unit",
        "tests.unit._helpers",
    )
    assert module is not None
    assert "from __future__ import annotations" in module.code


def test_load_or_create_conftest_module_synthesizes_when_absent() -> None:
    """_load_or_create_conftest_module parses a fresh stub for a missing path."""
    module = _load_or_create_conftest_module(_ABSENT_ROOT / "tests" / "conftest.py")
    assert module is not None


def test_load_or_create_conftest_module_includes_future_import() -> None:
    """The synthesized conftest stub carries the future-annotations import."""
    module = _load_or_create_conftest_module(_ABSENT_ROOT / "tests" / "conftest.py")
    assert module is not None
    assert "from __future__ import annotations" in module.code


def test_load_or_create_conftest_module_mentions_pytest_fixtures() -> None:
    """The synthesized conftest stub documents its auto-discovered-fixture purpose."""
    module = _load_or_create_conftest_module(_ABSENT_ROOT / "tests" / "conftest.py")
    assert module is not None
    assert "fixture" in module.code.lower()


@pytest.mark.parametrize("tier", ["unit", "integration", "e2e"])
def test_load_or_create_helpers_module_handles_each_canonical_tier(tier: str) -> None:
    """A helpers stub is synthesized for every canonical tier name."""
    module = _load_or_create_helpers_module(
        _ABSENT_ROOT / "tests" / tier / "_helpers.py",
        tier,
        f"tests.{tier}._helpers",
    )
    assert module is not None
    assert f"tests/{tier}" in module.code
