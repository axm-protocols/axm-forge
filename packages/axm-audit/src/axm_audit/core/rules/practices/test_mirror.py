"""Test-file mirror rule — every source module needs a test file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

__all__ = ["TestMirrorRule"]

_TEST_MIRROR_EXEMPT = {"__init__.py", "_version.py", "conftest.py", "py.typed"}


@dataclass
@register_rule("practices")
class TestMirrorRule(ProjectRule):
    """Check that every source module has a corresponding test file.

    For each ``src/<pkg>/foo.py``, looks for ``tests/**/test_foo.py``
    anywhere in the test tree (supports flat and nested layouts).

    Private modules (leading underscores) are matched with the prefix
    stripped: ``_facade.py`` matches ``test_facade.py`` or
    ``test__facade.py``.

    Scoring: 100 - (missing_count * 15), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_TEST_MIRROR"

    def check(self, project_path: Path) -> CheckResult:
        """Check test file coverage for source modules."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        tests_path = project_path / "tests"
        missing = self._find_untested_modules(src_path, tests_path)

        if not missing:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="All source modules have test files",
                severity=Severity.INFO,
            )

        score = max(0, 100 - len(missing) * 15)
        passed = score >= 90  # noqa: PLR2004

        hint_files = ", ".join(f"tests/test_{m}" for m in missing[:5])
        if len(missing) > 5:  # noqa: PLR2004
            hint_files += f" (+{len(missing) - 5} more)"

        text_files = " ".join(missing[:5])
        if len(missing) > 5:  # noqa: PLR2004
            text_files += f" (+{len(missing) - 5} more)"
        text_lines = [f"• untested: {text_files}"] if missing else []

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(missing)} source module(s) without tests",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"missing": missing},
            fix_hint=f"Create test files: {hint_files}",
            text="\n".join(text_lines) if text_lines else None,
        )

    @staticmethod
    def _collect_source_modules(src_path: Path) -> list[str]:
        """Collect non-exempt Python module basenames from ``src/``."""
        pkg_dirs = [
            d for d in src_path.iterdir() if d.is_dir() and d.name != "__pycache__"
        ]
        modules: list[str] = []
        for pkg_dir in pkg_dirs:
            for py_file in pkg_dir.rglob("*.py"):
                if py_file.name not in _TEST_MIRROR_EXEMPT:
                    modules.append(py_file.name)
        return modules

    @staticmethod
    def _collect_test_basenames(tests_path: Path) -> set[str]:
        """Collect all ``test_*.py`` basenames from the test tree."""
        if not tests_path.exists():
            return set()
        return {f.name for f in tests_path.rglob("test_*.py")}

    @classmethod
    def _find_untested_modules(
        cls,
        src_path: Path,
        tests_path: Path,
    ) -> list[str]:
        """Find source modules without corresponding test files."""
        source_modules = cls._collect_source_modules(src_path)
        if not source_modules:
            return []

        test_basenames = cls._collect_test_basenames(tests_path)

        missing: list[str] = []
        for name in sorted(set(source_modules)):
            stripped = name.lstrip("_")
            candidates = {f"test_{stripped}", f"test_{name}"}
            if not candidates & test_basenames:
                missing.append(name)
        return missing
