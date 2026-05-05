"""Test-file mirror rule — every source module needs a test file."""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

__all__ = ["MirrorRule"]

_TEST_MIRROR_EXEMPT = {
    "__init__.py",
    "__main__.py",
    "_version.py",
    "conftest.py",
    "py.typed",
}


@dataclass
@register_rule("practices")
class MirrorRule(ProjectRule):
    """Check the bidirectional 1:1 mapping between source modules and unit tests.

    Forward direction — for each ``src/<pkg>/foo.py``, looks for a
    ``test_foo.py`` under ``tests/`` (or ``tests/unit/`` when present).

    Reverse direction (orphan check) — for each ``tests/unit/<rel>/test_<name>.py``,
    requires that some package exposes ``src/<pkg>/<rel>/<name>.py``. Tests at the
    wrong nesting level or pointing to nonexistent source modules are flagged
    as orphans. Reverse check only walks ``tests/unit/`` — ``tests/integration/``
    and ``tests/e2e/`` are scenario-named and never flagged.

    Private modules (leading underscores) are matched with the prefix
    stripped: ``_facade.py`` matches ``test_facade.py`` or
    ``test__facade.py``.

    Exempt filenames (no test required): ``__init__.py``, ``__main__.py``,
    ``_version.py``, ``conftest.py``, ``py.typed``.

    Scoring: ``100 - (len(missing) + len(orphan)) * 15``, min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule (bidirectional mirror check)."""
        return "PRACTICE_TEST_MIRROR"

    def check(self, project_path: Path) -> CheckResult:
        """Check forward + reverse test/source mapping."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        tests_path = project_path / "tests"
        missing = self._find_untested_modules(src_path, tests_path)
        orphan = self._collect_orphan_tests(src_path, tests_path)

        if not missing and not orphan:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="All source modules have test files",
                severity=Severity.INFO,
                details={"missing": [], "orphan": []},
            )

        violations = len(missing) + len(orphan)
        score = max(0, 100 - violations * 15)
        passed = score >= 90  # noqa: PLR2004

        hint = self._build_fix_hint(src_path, missing, orphan)
        text = self._build_text(missing, orphan)
        message = self._build_message(missing, orphan)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"missing": missing, "orphan": orphan},
            fix_hint=hint,
            text=text,
        )

    @staticmethod
    def _build_message(missing: list[str], orphan: list[str]) -> str:
        """Build the summary message line."""
        parts = []
        if missing:
            parts.append(f"{len(missing)} source module(s) without tests")
        if orphan:
            parts.append(f"{len(orphan)} orphan test(s)")
        return "; ".join(parts) if parts else "All source modules have test files"

    @staticmethod
    def _build_text(missing: list[str], orphan: list[str]) -> str | None:
        """Build the multi-line text block (untested + orphan bullets)."""
        lines: list[str] = []
        if missing:
            shown = missing[:5]
            tail = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""  # noqa: PLR2004
            lines.append("• untested: " + " ".join(shown) + tail)
        if orphan:
            shown_o = orphan[:5]
            tail_o = f" (+{len(orphan) - 5} more)" if len(orphan) > 5 else ""  # noqa: PLR2004
            lines.append("• orphan: " + " ".join(shown_o) + tail_o)
        return "\n".join(lines) if lines else None

    @classmethod
    def _build_fix_hint(
        cls,
        src_path: Path,
        missing: list[str],
        orphan: list[str],
    ) -> str | None:
        """Build the fix hint covering both missing tests and orphan suggestions."""
        parts: list[str] = []
        if missing:
            files = ", ".join(f"tests/test_{m}" for m in missing[:5])
            if len(missing) > 5:  # noqa: PLR2004
                files += f" (+{len(missing) - 5} more)"
            parts.append(f"Create test files: {files}")
        if orphan:
            source_stems = sorted(
                {
                    Path(n).stem.lstrip("_")
                    for n in cls._collect_source_modules(src_path)
                }
            )
            for orphan_path in orphan[:5]:
                stem = Path(orphan_path).stem[len("test_") :]
                close = difflib.get_close_matches(stem, source_stems, n=1, cutoff=0.6)
                if close:
                    suggested = f"test_{close[0]}.py"
                    parts.append(
                        f"{orphan_path} → rename to {suggested} or merge into "
                        f"tests/unit/{suggested}"
                    )
                else:
                    parts.append(
                        f"{orphan_path} → delete or rename to a real source module"
                    )
            if len(orphan) > 5:  # noqa: PLR2004
                parts.append(f"(+{len(orphan) - 5} more orphans)")
        return "; ".join(parts) if parts else None

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
        """Collect ``test_*.py`` basenames eligible to satisfy the mirror rule.

        Mirror naming (1:1 with source modules) is a unit-level convention.
        Integration and e2e tests are scenario-named, so they must not count
        toward mirror coverage. If ``tests/unit/`` exists and contains test
        files, search there; otherwise fall back to the whole ``tests/`` tree
        (legacy flat layout) while still excluding ``integration/`` and
        ``e2e/`` subdirs.
        """
        if not tests_path.exists():
            return set()
        unit_path = tests_path / "unit"
        if unit_path.exists():
            unit_tests = {f.name for f in unit_path.rglob("test_*.py")}
            if unit_tests:
                return unit_tests
        return {
            f.name
            for f in tests_path.rglob("test_*.py")
            if "integration" not in f.parts and "e2e" not in f.parts
        }

    @staticmethod
    def _collect_unit_test_index(tests_path: Path) -> dict[str, set[str]]:
        """Index unit tests by rel directory; the ``test_`` prefix is stripped."""
        unit_path = tests_path / "unit"
        if not unit_path.is_dir():
            return {}
        index: dict[str, set[str]] = {}
        for test_file in unit_path.rglob("test_*.py"):
            if not test_file.is_file():
                continue
            rel_dir = test_file.parent.relative_to(unit_path).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir
            stem = test_file.stem[len("test_") :]
            bucket = index.setdefault(rel_dir, set())
            bucket.add(stem)
            bucket.add(stem.lstrip("_"))
        return index

    @classmethod
    def _find_untested_modules(
        cls,
        src_path: Path,
        tests_path: Path,
    ) -> list[str]:
        """Find source modules without corresponding test files.

        When ``tests/unit/`` is populated, the mirror is arborescence-aware:
        ``src/<pkg>/<rel>/<name>.py`` requires ``tests/unit/<rel>/test_<name>.py``.
        Otherwise (legacy flat layout, or empty ``tests/unit/``), basename
        matching is used.
        """
        if not src_path.is_dir():
            return []
        unit_index = cls._collect_unit_test_index(tests_path)
        use_arborescence = bool(unit_index)
        missing: list[str] = []
        seen: set[str] = set()
        for pkg_dir in sorted(src_path.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name == "__pycache__":
                continue
            for py_file in sorted(pkg_dir.rglob("*.py")):
                if py_file.name in _TEST_MIRROR_EXEMPT:
                    continue
                if py_file.name in seen:
                    continue
                seen.add(py_file.name)
                stem = py_file.stem
                if use_arborescence:
                    rel_dir = py_file.parent.relative_to(pkg_dir).as_posix()
                    rel_dir = "" if rel_dir == "." else rel_dir
                    available = unit_index.get(rel_dir, set())
                    if not {stem, stem.lstrip("_")} & available:
                        missing.append(py_file.name)
                else:
                    test_basenames = cls._collect_test_basenames(tests_path)
                    candidates = {f"test_{stem.lstrip('_')}.py", f"test_{stem}.py"}
                    if not candidates & test_basenames:
                        missing.append(py_file.name)
        return sorted(set(missing))

    @staticmethod
    def _collect_source_index(src_path: Path) -> dict[str, set[str]]:
        """Index source modules as ``{rel_dir: {stem variants}}``.

        Each non-exempt ``src/<pkg>/<rel>/<basename>.py`` contributes one entry
        per package: key = ``<rel>`` (POSIX, empty for package root), value
        contains both the original stem and the underscore-stripped stem so
        that ``_facade.py`` matches a ``test_facade.py`` test.
        """
        if not src_path.is_dir():
            return {}
        index: dict[str, set[str]] = {}
        for pkg_dir in src_path.iterdir():
            if not pkg_dir.is_dir() or pkg_dir.name == "__pycache__":
                continue
            for py_file in pkg_dir.rglob("*.py"):
                if py_file.name in _TEST_MIRROR_EXEMPT:
                    continue
                rel_dir = py_file.parent.relative_to(pkg_dir).as_posix()
                rel_dir = "" if rel_dir == "." else rel_dir
                stem = py_file.stem
                bucket = index.setdefault(rel_dir, set())
                bucket.add(stem)
                bucket.add(stem.lstrip("_"))
        return index

    @classmethod
    def _collect_orphan_tests(
        cls,
        src_path: Path,
        tests_path: Path,
    ) -> list[str]:
        """List ``tests/unit/`` test files with no matching source module.

        Walks ``tests/unit/**/test_*.py`` and flags each whose
        ``(rel_dir, stem)`` does not correspond to any source module under
        ``src/<pkg>/<rel_dir>/<stem>.py`` (with optional leading underscores).
        Returns POSIX ``tests/unit``-rooted paths sorted for determinism.
        Always returns ``[]`` when ``tests/unit/`` is absent.
        """
        unit_path = tests_path / "unit"
        if not unit_path.is_dir():
            return []
        src_index = cls._collect_source_index(src_path)
        orphans: list[str] = []
        for test_file in unit_path.rglob("test_*.py"):
            if not test_file.is_file():
                continue
            rel_dir = test_file.parent.relative_to(unit_path).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir
            test_stem = test_file.stem[len("test_") :]
            candidates = {test_stem, test_stem.lstrip("_")}
            available = src_index.get(rel_dir, set())
            if not candidates & available:
                rel_to_unit = test_file.relative_to(tests_path).as_posix()
                orphans.append(f"tests/{rel_to_unit}")
        return sorted(orphans)
