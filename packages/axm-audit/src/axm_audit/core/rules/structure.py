"""Structure rules — file and directory existence checks."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

_PYRAMID_DIRS: tuple[str, ...] = ("tests/unit", "tests/integration", "tests/e2e")
_REQUIRED_MARKERS: tuple[str, ...] = ("integration", "e2e")
_AXMTOOL_IMPORT = re.compile(
    r"(?m)^\s*from\s+axm(\.|_)[\w.]*\s+import\s+[^#\n]*AXMTool"
)


def _is_self_contained(project_path: Path) -> bool:
    """Return True when the package exposes a CLI or an AXMTool subclass.

    Detection order: ``[project.scripts]`` in pyproject.toml, then an
    ``AXMTool`` import scanned across ``src/**/*.py``. Errors fall back to
    treating the package as self-contained — the stricter default.
    """
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text())
        except (tomllib.TOMLDecodeError, OSError):
            return True
        if data.get("project", {}).get("scripts"):
            return True
    src = project_path / "src"
    if not src.exists():
        return False
    for py_file in src.rglob("*.py"):
        try:
            text = py_file.read_text()
        except OSError:
            continue
        if _AXMTOOL_IMPORT.search(text):
            return True
    return False


@dataclass
class FileExistsRule(ProjectRule):
    """Rule that checks if a required file exists.

    Not decorated with ``@register_rule`` — this rule is consumed by
    ``axm-init`` checklist checks, not auto-discovered during audits.
    The ``category`` property is set manually for the same reason.
    """

    file_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"FILE_EXISTS_{self.file_name}"

    @property
    def category(self) -> str:
        """Scoring category for this rule."""
        return "structure"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the file exists in the project.

        Returns a passing result when the file is present, or a failing
        result with ``fix_hint="touch {file_name}"`` when missing.
        """
        target = project_path / self.file_name
        if target.exists() and target.is_file():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"{self.file_name} exists",
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.file_name} not found",
            fix_hint=f"touch {self.file_name}",
        )


@dataclass
class DirectoryExistsRule(ProjectRule):
    """Rule that checks if a required directory exists.

    Not decorated with ``@register_rule`` — this rule is consumed by
    ``axm-init`` checklist checks, not auto-discovered during audits.
    The ``category`` property is set manually for the same reason.
    """

    dir_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"DIR_EXISTS_{self.dir_name}"

    @property
    def category(self) -> str:
        """Scoring category for this rule."""
        return "structure"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the directory exists in the project.

        Returns a passing result when the directory is present, or a failing
        result with ``fix_hint="mkdir {dir_name}"`` when missing.
        """
        target = project_path / self.dir_name
        if target.exists() and target.is_dir():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"{self.dir_name}/ exists",
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.dir_name}/ not found",
            fix_hint=f"mkdir {self.dir_name}",
        )


# Fields to check in pyproject.toml [project] section
_REQUIRED_FIELDS = ("name", "description", "requires-python", "license", "authors")
_OPTIONAL_FIELDS = ("classifiers", "readme")
_TOTAL_FIELDS = 9  # required(5) + version + urls + optional(2)


def _check_fields(project: dict[str, Any]) -> tuple[int, list[str]]:
    """Check present PEP 621 fields in project table.

    Returns (present_count, missing_field_names).
    """
    missing: list[str] = [f for f in _REQUIRED_FIELDS if f not in project]

    # Version: static or dynamic
    has_version = "version" in project or "version" in project.get("dynamic", [])
    if not has_version:
        missing.append("version")

    # URLs section
    if not project.get("urls"):
        missing.append("urls")

    # Optional fields
    missing.extend(f for f in _OPTIONAL_FIELDS if f not in project)

    present = _TOTAL_FIELDS - len(missing)
    return present, missing


@dataclass
@register_rule("structure")
class TestsPyramidRule(ProjectRule):
    """Verify the 3-level test pyramid layout and pytest markers.

    Checks that ``tests/unit/``, ``tests/integration/`` and ``tests/e2e/``
    exist (``tests/e2e/`` is optional for library packages) and that
    ``pyproject.toml`` declares the ``integration`` and ``e2e`` pytest
    markers required by the project's strict-markers policy.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "STRUCTURE_TESTS_PYRAMID"

    def check(self, project_path: Path) -> CheckResult:
        """Check the test pyramid layout and required markers."""
        if not (project_path / "tests").exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="tests/ not found",
                severity=Severity.ERROR,
                fix_hint="mkdir -p " + " ".join(_PYRAMID_DIRS),
            )

        self_contained = _is_self_contained(project_path)
        required_dirs, required_markers = _pyramid_requirements(self_contained)
        missing_dirs = [d for d in required_dirs if not (project_path / d).is_dir()]
        missing_markers = _missing_markers(project_path, required_markers)

        if not missing_dirs and not missing_markers:
            present = ", ".join(d.split("/")[-1] for d in _PYRAMID_DIRS)
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"pyramid layout ok: {present}",
                details={"score": 100, "self_contained": self_contained},
            )

        return _pyramid_failure(
            self.rule_id, missing_dirs, missing_markers, self_contained
        )


def _pyramid_requirements(self_contained: bool) -> tuple[list[str], list[str]]:
    """Return (required_dirs, required_markers) based on package type."""
    if self_contained:
        return list(_PYRAMID_DIRS), list(_REQUIRED_MARKERS)
    dirs = [d for d in _PYRAMID_DIRS if d != "tests/e2e"]
    markers = [m for m in _REQUIRED_MARKERS if m != "e2e"]
    return dirs, markers


def _pyramid_failure(
    rule_id: str,
    missing_dirs: list[str],
    missing_markers: list[str],
    self_contained: bool,
) -> CheckResult:
    """Build a failing CheckResult describing missing dirs and markers."""
    parts: list[str] = []
    fix_parts: list[str] = []
    if missing_dirs:
        parts.append("missing dirs: " + ", ".join(missing_dirs))
        fix_parts.append("mkdir -p " + " ".join(missing_dirs))
    if missing_markers:
        parts.append("missing markers: " + ", ".join(missing_markers))
        fix_parts.append(
            "declare markers in [tool.pytest.ini_options].markers: "
            + ", ".join(missing_markers)
        )
    return CheckResult(
        rule_id=rule_id,
        passed=False,
        message="; ".join(parts),
        severity=Severity.WARNING,
        details={
            "score": 0,
            "missing_dirs": missing_dirs,
            "missing_markers": missing_markers,
            "self_contained": self_contained,
        },
        fix_hint=" && ".join(fix_parts),
    )


def _missing_markers(project_path: Path, required: list[str]) -> list[str]:
    """Return required markers not declared in pyproject.toml.

    Returns the full required list if pyproject.toml is missing or invalid,
    preserving strictness rather than silently passing.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return list(required)
    try:
        data = tomllib.loads(pyproject.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return list(required)
    markers = (
        data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
    )
    declared: set[str] = set()
    for entry in markers:
        if isinstance(entry, str):
            name = entry.split(":", 1)[0].strip()
            if name:
                declared.add(name)
    return [m for m in required if m not in declared]


@dataclass
@register_rule("structure")
class PyprojectCompletenessRule(ProjectRule):
    """Validate PEP 621 field completeness in pyproject.toml.

    Checks 9 fields: name, version/dynamic, description, requires-python,
    license, authors, classifiers, urls, readme.
    Scoring: (fields_present / 9) x 100.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "STRUCTURE_PYPROJECT"

    def check(self, project_path: Path) -> CheckResult:
        """Check pyproject.toml completeness."""
        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="pyproject.toml not found",
                severity=Severity.ERROR,
                details={"fields_present": 0, "total_fields": 9, "score": 0},
                fix_hint="Create pyproject.toml with PEP 621 metadata",
            )

        try:
            data = tomllib.loads(pyproject_path.read_text())
        except (tomllib.TOMLDecodeError, OSError):
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="pyproject.toml parse error",
                severity=Severity.ERROR,
                details={"fields_present": 0, "total_fields": 9, "score": 0},
                fix_hint="Fix pyproject.toml syntax",
            )

        present, missing = _check_fields(data.get("project", {}))
        score = int((present / _TOTAL_FIELDS) * 100)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= PASS_THRESHOLD,
            message=f"pyproject.toml completeness: {present}/{_TOTAL_FIELDS} fields",
            severity=Severity.WARNING if score < PASS_THRESHOLD else Severity.INFO,
            text=f"\u2022 missing: {', '.join(missing)}" if missing else None,
            details={
                "fields_present": present,
                "total_fields": _TOTAL_FIELDS,
                "score": score,
                "missing": missing,
            },
            fix_hint=(
                "Add missing PEP 621 fields to [project]"
                if score < PASS_THRESHOLD
                else None
            ),
        )
