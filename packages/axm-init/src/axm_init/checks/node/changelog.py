"""Node changelog gold-standard checks.

Ports the Python ``checks.changelog`` convention: the changelog is generated
from conventional commits (changesets / git-cliff / release-please), so a
hand-maintained ``CHANGELOG.md`` is an anti-pattern. We accept any of the
recognised generators as evidence the changelog is automated.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_changelog_automated"]


def _has_changeset_tooling(project: Path) -> bool:
    """Return True if a changelog generator is configured."""
    if (project / ".changeset").is_dir():
        return True
    if (project / "cliff.toml").is_file():
        return True
    if (project / ".release-please-manifest.json").is_file():
        return True
    pkg = project / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    dev = data.get("devDependencies") if isinstance(data, dict) else None
    return isinstance(dev, dict) and any(
        name in dev for name in ("@changesets/cli", "git-cliff", "release-please")
    )


def check_changelog_automated(project: Path) -> CheckResult:
    """Check: the changelog is automated (no hand-maintained CHANGELOG.md)."""
    has_tooling = _has_changeset_tooling(project)
    has_manual = (project / "CHANGELOG.md").is_file()
    # A manual CHANGELOG.md is only an issue when no generator is configured.
    if has_manual and not has_tooling:
        return CheckResult(
            name="changelog.changelog_automated",
            category="changelog",
            passed=False,
            weight=2,
            message="Manual CHANGELOG.md without a generator",
            details=["Use changesets / git-cliff / release-please"],
            fix="Adopt @changesets/cli (or git-cliff) to generate the changelog.",
        )
    if not has_tooling:
        return CheckResult(
            name="changelog.changelog_automated",
            category="changelog",
            passed=False,
            weight=2,
            message="No changelog generator configured",
            details=[],
            fix="Add @changesets/cli (or git-cliff) for an automated changelog.",
        )
    return CheckResult(
        name="changelog.changelog_automated",
        category="changelog",
        passed=True,
        weight=2,
        message="Changelog is automated",
        details=[],
        fix="",
    )
