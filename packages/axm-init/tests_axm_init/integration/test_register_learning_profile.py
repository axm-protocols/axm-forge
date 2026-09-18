from __future__ import annotations

import importlib
import tomllib
from types import ModuleType

import pytest


def _learning_profile_module() -> ModuleType:
    return importlib.import_module("axm_init.core.learning_profile")


def _write_project(root: object) -> None:
    project = root / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\ndependencies = ["httpx>=0.27"]\n',
        encoding="utf-8",
    )


@pytest.mark.integration
def test_register_learning_profile_writes_merged_project(tmp_path) -> None:
    """AC4: registration persists the profile and generated entry point."""
    learning_profile = _learning_profile_module()
    _write_project(tmp_path)

    learning_profile.register_learning_profile(
        tmp_path, domain="vision", module_name="axm_demo"
    )
    parsed = tomllib.loads((tmp_path / "pyproject.toml").read_text(encoding="utf-8"))

    assert parsed["tool"]["axm-init"]["learning"]["domain"] == "vision"
    assert parsed["project"]["entry-points"]["axm.tools"]["axm_demo_train"] == (
        "axm_demo.learning.tool:TrainingTool"
    )


@pytest.mark.integration
def test_register_learning_profile_refuses_domain_conflict_before_write(
    tmp_path,
) -> None:
    """AC4: a conflicting domain names both owners and cannot mutate bytes."""
    learning_profile = _learning_profile_module()
    _write_project(tmp_path)
    project = tmp_path / "pyproject.toml"
    learning_profile.register_learning_profile(
        tmp_path, domain="vision", module_name="axm_demo"
    )
    before = project.read_bytes()

    with pytest.raises(ValueError) as error:
        learning_profile.register_learning_profile(
            tmp_path, domain="language", module_name="axm_demo"
        )

    assert "vision" in str(error.value)
    assert "language" in str(error.value)
    assert project.read_bytes() == before
