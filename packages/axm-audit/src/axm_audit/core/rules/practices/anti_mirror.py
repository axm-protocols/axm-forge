"""Anti-mirror rule — integration/e2e tests must not be named after source modules.

Industry convention (pyOpenSci, Real Python, the Pyramid testing literature):
``tests/integration/`` and ``tests/e2e/`` test files describe a *scenario* or a
*user action*, not a source module. A ``tests/integration/test_foo.py`` whose
basename collides with ``src/<pkg>/.../foo.py`` is almost always a misplaced
unit test — it duplicates the unit-mirror surface (``MirrorRule``) and obscures
the behaviour the integration suite is supposed to verify.

This rule walks ``tests/integration/**/test_*.py`` and ``tests/e2e/**/test_*.py``
and flags every test file whose ``test_<name>.py`` shadows a source module
basename. ``tests/unit/`` is *never* walked here — that's ``MirrorRule``'s job.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.practices.mirror import (
    _TEST_MIRROR_EXEMPT,
    _glob_segments_match,
    _load_mirror_config,
)
from axm_audit.core.rules.test_quality.file_naming import _verdict_for_file
from axm_audit.models.results import CheckResult, Severity

__all__ = ["AntiMirrorRule"]

_SCAN_DIRS = ("integration", "e2e")


def _collect_source_basenames(src_path: Path, exempt_paths: list[str]) -> set[str]:
    """Return source module basenames, excluding exempt-path matches."""
    if not src_path.is_dir():
        return set()
    out: set[str] = set()
    for pkg_dir in src_path.iterdir():
        if not pkg_dir.is_dir() or pkg_dir.name == "__pycache__":
            continue
        for py_file in pkg_dir.rglob("*.py"):
            if py_file.name in _TEST_MIRROR_EXEMPT:
                continue
            rel_to_pkg = py_file.relative_to(pkg_dir).as_posix()
            if exempt_paths and any(
                _glob_segments_match(p.split("/"), rel_to_pkg.split("/"))
                for p in exempt_paths
            ):
                continue
            out.add(py_file.name)
    return out


def _collect_anti_mirror_violations(
    tests_path: Path, source_basenames: set[str]
) -> list[str]:
    """Return tests/-relative paths of integration/e2e tests shadowing src."""
    if not tests_path.is_dir():
        return []
    violations: list[str] = []
    for sub in _SCAN_DIRS:
        scan_root = tests_path / sub
        if not scan_root.is_dir():
            continue
        for test_file in scan_root.rglob("test_*.py"):
            if not test_file.is_file():
                continue
            stem = test_file.stem
            if not stem.startswith("test_"):
                continue
            candidate = stem[len("test_") :] + ".py"
            if candidate in source_basenames:
                rel = test_file.relative_to(tests_path).as_posix()
                violations.append(f"tests/{rel}")
    return sorted(set(violations))


def _drop_k1_canonical_collisions(
    violations: list[str], project_path: Path
) -> list[str]:
    """Suppress violations where the stem equals the canonical K=1 name.

    A ``tests/integration/test_foo.py`` whose tests cover exactly one
    first-party symbol ``foo`` is the canonical K=1 form FILE_NAMING
    would emit. The collision with ``src/<pkg>/foo.py`` is a false
    positive for anti-mirror: renaming would re-fire NAME_MISMATCH.
    """
    if not violations:
        return violations
    kept: list[str] = []
    for rel in violations:
        test_file = project_path / rel
        verdict = _verdict_for_file(test_file, project_path)
        if (
            verdict is not None
            and verdict.canonical == test_file.name
            and len(verdict.distinct_non_empty_tuples) <= 1
        ):
            continue
        kept.append(rel)
    return kept


@dataclass
@register_rule("practices")
class AntiMirrorRule(ProjectRule):
    """Flag integration/e2e tests named after source modules.

    Integration and e2e tests are scenario-named by convention. A
    ``tests/integration/test_foo.py`` that mirrors ``src/<pkg>/foo.py`` is
    almost always a misplaced unit test — promote it to ``tests/unit/`` or
    rename to describe the verified scenario.

    Sources matched by ``[tool.axm-audit.mirror].exempt_paths`` are excluded:
    a CLI-wrapper module like ``commands/data.py`` exempted by AXM-1666 is
    legitimately covered by ``tests/integration/test_data.py``.

    Scoring: ``max(0, 100 - len(violations) * 15)``; ``passed = score >= 90``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_TEST_SCENARIO_NAMING"

    def check(self, project_path: Path) -> CheckResult:
        """Walk integration/e2e and flag tests named after source modules."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        tests_path = project_path / "tests"
        if (
            not (tests_path / "integration").is_dir()
            and not (tests_path / "e2e").is_dir()
        ):
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No integration or e2e tests to check",
                severity=Severity.INFO,
                score=100,
                details={"anti_mirror": []},
            )

        config = _load_mirror_config(project_path)
        if config.error is not None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="Invalid mirror config",
                severity=Severity.WARNING,
                score=0,
                details={"anti_mirror": []},
                fix_hint=config.error,
            )

        src_path = project_path / "src"
        source_basenames = _collect_source_basenames(src_path, config.exempt_paths)
        violations = _collect_anti_mirror_violations(tests_path, source_basenames)
        violations = _drop_k1_canonical_collisions(violations, project_path)

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No anti-mirror naming violations",
                severity=Severity.INFO,
                score=100,
                details={"anti_mirror": []},
            )

        score = max(0, 100 - len(violations) * 15)
        passed = score >= 90  # noqa: PLR2004

        shown = violations[:5]
        tail = (
            f" (+{len(violations) - 5} more)" if len(violations) > 5 else ""  # noqa: PLR2004
        )
        text = "• anti-mirror: " + " ".join(shown) + tail

        first = violations[0]
        fix_hint = (
            f"{first} → rename to test_<scenario>.py describing what the test "
            "verifies (scenario-named, not source-mirrored)"
        )

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                f"{len(violations)} integration/e2e test(s) named after source modules"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"anti_mirror": violations},
            fix_hint=fix_hint,
            text=text,
        )
