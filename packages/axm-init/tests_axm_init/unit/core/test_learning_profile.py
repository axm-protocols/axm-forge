from __future__ import annotations

import importlib
import tomllib
from types import ModuleType

LEARNING_DISTRIBUTIONS = ("axm-learning", "axm-fit", "axm-tune")


def _learning_profile_module() -> ModuleType:
    return importlib.import_module("axm_init.core.learning_profile")


def _metadata() -> str:
    return """[project]
name = "demo"
dependencies = ["httpx>=0.27"]

[tool.ruff]
line-length = 99
"""


def test_merge_writes_profile_and_preserves_existing_tables() -> None:
    """AC1: the learning profile is typed and existing tables stay verbatim."""
    learning_profile = _learning_profile_module()
    ruff_table = "[tool.ruff]\nline-length = 99\n"

    merged = learning_profile.merge_learning_metadata(
        _metadata(), domain="vision", module_name="axm_demo"
    )
    parsed = tomllib.loads(merged)
    profile = parsed["tool"]["axm-init"]["learning"]

    assert profile["domain"] == "vision"
    assert isinstance(profile["schema_version"], int)
    assert ruff_table in merged


def test_merge_declares_learning_distributions_without_dropping_existing() -> None:
    """AC2: all learning distributions join the existing dependencies."""
    learning_profile = _learning_profile_module()

    merged = learning_profile.merge_learning_metadata(
        _metadata(), domain="vision", module_name="axm_demo"
    )
    dependencies = tomllib.loads(merged)["project"]["dependencies"]

    assert "httpx>=0.27" in dependencies
    assert all(distribution in dependencies for distribution in LEARNING_DISTRIBUTIONS)


def test_merge_is_idempotent_with_one_entry_per_distribution() -> None:
    """AC2: reapplying the merge is byte-idempotent and adds no duplicate."""
    learning_profile = _learning_profile_module()

    first = learning_profile.merge_learning_metadata(
        _metadata(), domain="vision", module_name="axm_demo"
    )
    second = learning_profile.merge_learning_metadata(
        first, domain="vision", module_name="axm_demo"
    )
    dependencies = tomllib.loads(second)["project"]["dependencies"]

    assert second == first
    assert "httpx>=0.27" in dependencies
    assert all(dependencies.count(item) == 1 for item in LEARNING_DISTRIBUTIONS)


def test_merge_declares_generated_training_entry_point() -> None:
    """AC3: the generated module exposes its training tool to axm.tools."""
    learning_profile = _learning_profile_module()

    merged = learning_profile.merge_learning_metadata(
        _metadata(), domain="vision", module_name="axm_demo"
    )
    entry_points = tomllib.loads(merged)["project"]["entry-points"]["axm.tools"]

    assert entry_points["axm_demo_train"] == ("axm_demo.learning.tool:TrainingTool")
