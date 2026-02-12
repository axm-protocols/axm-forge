"""Structure rules — file and directory existence checks."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


@dataclass
class FileExistsRule(ProjectRule):
    """Rule that checks if a required file exists."""

    file_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"FILE_EXISTS_{self.file_name}"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the file exists in the project."""
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
        )


@dataclass
class DirectoryExistsRule(ProjectRule):
    """Rule that checks if a required directory exists."""

    dir_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"DIR_EXISTS_{self.dir_name}"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the directory exists in the project."""
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
        )


# Fields to check in pyproject.toml [project] section
_REQUIRED_FIELDS = ("name", "description", "requires-python", "license", "authors")
_OPTIONAL_FIELDS = ("classifiers", "readme")
_TOTAL_FIELDS = 9  # required(5) + version + urls + optional(2)


def _count_fields(project: dict[str, Any]) -> int:
    """Count present PEP 621 fields in project table."""
    present = sum(1 for f in _REQUIRED_FIELDS if f in project)

    # Version: static or dynamic
    if "version" in project or "version" in project.get("dynamic", []):
        present += 1

    # URLs section
    if project.get("urls"):
        present += 1

    # Optional fields
    present += sum(1 for f in _OPTIONAL_FIELDS if f in project)
    return present


@dataclass
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

        present = _count_fields(data.get("project", {}))
        score = int((present / _TOTAL_FIELDS) * 100)

        return CheckResult(
            rule_id=self.rule_id,
            passed=score >= 80,
            message=f"pyproject.toml completeness: {present}/{_TOTAL_FIELDS} fields",
            severity=Severity.WARNING if score < 80 else Severity.INFO,
            details={
                "fields_present": present,
                "total_fields": _TOTAL_FIELDS,
                "score": score,
            },
            fix_hint=(
                "Add missing PEP 621 fields to [project]" if score < 80 else None
            ),
        )
