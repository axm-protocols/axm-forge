from __future__ import annotations

from pathlib import Path
from typing import cast

from axm_init.checks._utils import TomlTable, requires_toml, section
from axm_init.models.check import CheckResult

__all__ = ["check_learning_profile"]

# A learning profile is opt-in metadata. Keep this category out of the default
# package-wide inventory so projects without a profile retain their historical
# check counts and grades; CheckEngine discovers it when explicitly selected.
__axm_explicit_only__ = True

_SUPPORTED_SCHEMA_VERSION = 1
_GENERATED_CONFIG_FILES = ("study.toml", "training.toml")
_FIX = "Regenerate the learning profile to restore its configuration files."


@requires_toml(
    "learning.profile",
    "learning",
    2,
    _FIX,
)
def _check_learning_profile(project: Path, data: TomlTable) -> CheckResult:
    """Check the generated configuration for a declared learning profile."""
    tool = section(data, "tool")
    axm_init = section(tool, "axm-init")
    if "learning" not in axm_init:
        return CheckResult(
            name="learning.profile",
            category="learning",
            passed=True,
            weight=0,
            message="No learning profile declared",
            details=[],
            fix="",
        )

    profile = section(axm_init, "learning")
    domain = profile.get("domain")
    schema_version = profile.get("schema_version")
    problems: list[str] = []
    if not isinstance(domain, str) or not domain:
        problems.append("Missing or invalid domain in [tool.axm-init.learning]")
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        problems.append(
            "Unsupported schema_version in [tool.axm-init.learning]: "
            f"expected {_SUPPORTED_SCHEMA_VERSION}, got {schema_version!r}"
        )

    missing = [
        name for name in _GENERATED_CONFIG_FILES if not (project / name).is_file()
    ]
    problems.extend(f"Missing generated configuration file: {name}" for name in missing)

    if problems:
        return CheckResult(
            name="learning.profile",
            category="learning",
            passed=False,
            weight=2,
            message="Learning profile configuration is incomplete",
            details=problems,
            fix=_FIX,
        )

    return CheckResult(
        name="learning.profile",
        category="learning",
        passed=True,
        weight=2,
        message=f"Learning profile for {domain} is configured",
        details=[],
        fix="",
    )


def check_learning_profile(project: Path) -> CheckResult:
    """Delegate explicit learning checks to the installed domain provider."""
    from axm_init.scaffolding import load_provider

    hook = getattr(load_provider("learning"), "check_learning_profile", None)
    if callable(hook):
        return cast(CheckResult, hook(project))
    return _check_learning_profile(project)


# Preserve the historical table-level callable for direct rule consumers.
check_learning_profile.__wrapped__ = _check_learning_profile.__wrapped__  # type: ignore[attr-defined]
