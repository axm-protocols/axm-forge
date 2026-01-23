"""Practice rules — code quality patterns via AST and regex."""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from axm_audit.core.rules.architecture import _get_python_files, _parse_file_safe
from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


@dataclass
class DocstringCoverageRule(ProjectRule):
    """Calculate docstring coverage for public functions.

    Public functions are those not starting with underscore.
    """

    min_coverage: float = 0.80

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_DOCSTRING"

    def check(self, project_path: Path) -> CheckResult:
        """Check docstring coverage in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return self._empty_result()

        documented, missing = self._analyze_docstrings(src_path)
        total = documented + len(missing)
        coverage = documented / total if total > 0 else 1.0
        passed = coverage >= self.min_coverage
        score = int(coverage * 100)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Docstring coverage: {coverage:.0%} ({documented}/{total})",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "coverage": round(coverage, 2),
                "total": total,
                "documented": documented,
                "missing": missing[:10],  # Top 10 missing
                "score": score,
            },
            fix_hint="Add docstrings to public functions" if missing else None,
        )

    def _empty_result(self) -> CheckResult:
        """Return result when src/ doesn't exist."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="src/ directory not found",
            severity=Severity.INFO,
            details={"coverage": 1.0, "total": 0, "documented": 0, "missing": []},
        )

    def _analyze_docstrings(self, src_path: Path) -> tuple[int, list[str]]:
        """Analyze docstring coverage in source files.

        Returns:
            Tuple of (documented_count, list of missing function locations).
        """
        documented = 0
        missing: list[str] = []

        for path in _get_python_files(src_path):
            tree = _parse_file_safe(path)
            if tree is None:
                continue

            rel_path = path.relative_to(src_path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if node.name.startswith("_"):
                    continue

                if self._has_docstring(node):
                    documented += 1
                else:
                    missing.append(f"{rel_path}:{node.name}")

        return documented, missing

    def _has_docstring(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function node has a docstring."""
        if not node.body:
            return False
        first = node.body[0]
        return (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )


@dataclass
class BareExceptRule(ProjectRule):
    """Detect bare except clauses (except: without type)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BARE_EXCEPT"

    def check(self, project_path: Path) -> CheckResult:
        """Check for bare except clauses in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"bare_except_count": 0, "locations": []},
            )

        bare_excepts: list[dict[str, str | int]] = []
        py_files = _get_python_files(src_path)

        for path in py_files:
            tree = _parse_file_safe(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    # type is None means bare except:
                    if node.type is None:
                        bare_excepts.append(
                            {
                                "file": str(path.relative_to(src_path)),
                                "line": node.lineno,
                            }
                        )

        count = len(bare_excepts)
        passed = count == 0
        score = max(0, 100 - count * 20)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} bare except(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "bare_except_count": count,
                "locations": bare_excepts,
                "score": score,
            },
            fix_hint="Use specific exception types (e.g., except ValueError:)"
            if not passed
            else None,
        )


@dataclass
class SecurityPatternRule(ProjectRule):
    """Detect hardcoded secrets via regex patterns."""

    patterns: list[str] = field(
        default_factory=lambda: [
            r"password\s*=\s*[\"'][^\"']+[\"']",
            r"secret\s*=\s*[\"'][^\"']+[\"']",
            r"api_key\s*=\s*[\"'][^\"']+[\"']",
            r"token\s*=\s*[\"'][^\"']+[\"']",
        ]
    )

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_SECURITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check for hardcoded secrets in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"secret_count": 0, "matches": []},
            )

        matches: list[dict[str, str | int]] = []
        py_files = _get_python_files(src_path)

        for path in py_files:
            try:
                content = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for pattern in self.patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # Find line number
                    line_num = content[: match.start()].count("\n") + 1
                    matches.append(
                        {
                            "file": str(path.relative_to(src_path)),
                            "line": line_num,
                            "pattern": pattern.split(r"\s*")[0],  # Just the key name
                        }
                    )

        count = len(matches)
        passed = count == 0
        score = max(0, 100 - count * 25)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} potential secret(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            details={"secret_count": count, "matches": matches, "score": score},
            fix_hint="Use environment variables or secret managers"
            if not passed
            else None,
        )
