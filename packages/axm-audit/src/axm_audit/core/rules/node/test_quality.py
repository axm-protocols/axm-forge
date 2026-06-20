"""Node test-quality rules — the AXM-specific test-hygiene invariants for TS.

These have no off-the-shelf node tool; they port the *intent* of the Python
``test_quality`` rules to TypeScript, adapted to node conventions:

* **mirror** — every source module has a test. In node the de-facto idiom is a
  *colocated* ``foo.test.ts`` next to ``foo.ts`` (not a separate ``tests/`` tree),
  so the node mirror is sibling-based.
* **pyramid level** — colocated ``*.test.ts`` are unit; tests under ``tests/`` or
  ``e2e/`` / ``*.spec.ts`` with Playwright are higher levels. We flag colocated
  unit tests that do real I/O (a soft signal they belong in integration/e2e).
* **tautology** — weak assertions (``expect(true)…``, ``expect(x).toBe(x)``).
* **duplicate** — identical test bodies.

The first two are file-system + light source signals; the last two read the TS
AST through axm-ast (``analyze_package``), which now supports ``.ts``.
"""

from __future__ import annotations

import re
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import PASS_THRESHOLD, ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "NodeTestDuplicateRule",
    "NodeTestMirrorRule",
    "NodeTestPyramidRule",
    "NodeTestTautologyRule",
]

# Source files that never need a test (entry points, config, type decls).
_MIRROR_EXEMPT_STEMS = frozenset({"index", "main", "app", "vite-env"})
_TEST_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
_DECL_SUFFIX = ".d.ts"


def _is_test_file(path: Path) -> bool:
    """Return True if *path* is a test/spec file (by node naming convention)."""
    return any(path.name.endswith(s) for s in _TEST_SUFFIXES)


def _is_source_file(path: Path) -> bool:
    """Return True if *path* is a TS source module (not a test or .d.ts)."""
    if path.name.endswith(_DECL_SUFFIX) or _is_test_file(path):
        return False
    return path.suffix in (".ts", ".tsx")


def _iter_source_files(src: Path) -> list[Path]:
    """List TS source modules under *src*, skipping tests and declarations."""
    if not src.is_dir():
        return []
    return sorted(p for p in src.rglob("*") if p.is_file() and _is_source_file(p))


def _src_dir(project_path: Path) -> Path | None:
    """Return the project's source dir (``src/`` if present, else the root)."""
    src = project_path / "src"
    if src.is_dir():
        return src
    if (project_path / "package.json").is_file():
        return project_path
    return None


def _no_package_json(project_path: Path, rule_id: str) -> CheckResult:
    """Build the skip result for a non-node directory."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="No package.json — skipped",
        severity=Severity.INFO,
        score=100,
    )


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestMirrorRule(ProjectRule):
    """Every source module has a colocated ``*.test.ts`` (node mirror idiom)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_MIRROR"

    def check(self, project_path: Path) -> CheckResult:
        """Flag source modules with no sibling test file."""
        src = _src_dir(project_path)
        if src is None:
            return _no_package_json(project_path, self.rule_id)
        missing: list[str] = []
        for source in _iter_source_files(src):
            if source.stem in _MIRROR_EXEMPT_STEMS:
                continue
            if not self._has_sibling_test(source):
                missing.append(source.relative_to(src).as_posix())
        score = max(0, 100 - len(missing) * 15)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "All source modules have colocated tests"
                if not missing
                else f"{len(missing)} module(s) without a colocated test"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"missing": missing[:20]},
            fix_hint=(
                f"Add colocated tests: {', '.join(missing[:5])}" if missing else None
            ),
        )

    @staticmethod
    def _has_sibling_test(source: Path) -> bool:
        """Return True if a ``<stem>.test.ts``/``.spec.ts`` sits beside *source*."""
        stem = source.stem
        for suffix in _TEST_SUFFIXES:
            if (source.parent / f"{stem}{suffix}").is_file():
                return True
        return False


# Heuristic real-I/O signals for the pyramid level of a colocated unit test.
_REAL_IO = re.compile(
    r"\b(fs\.|readFileSync|writeFileSync|fetch\(|http\.|net\.|child_process|"
    r"execSync|spawnSync)\b"
)


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestPyramidRule(ProjectRule):
    """Colocated ``*.test.ts`` are unit tests; flag ones doing real I/O.

    A colocated unit test that touches the filesystem/network/subprocess is a
    soft signal it belongs in ``tests/integration`` or ``tests/e2e`` instead.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_PYRAMID_LEVEL"

    def check(self, project_path: Path) -> CheckResult:
        """Flag colocated unit tests that perform real I/O."""
        src = _src_dir(project_path)
        if src is None:
            return _no_package_json(project_path, self.rule_id)
        misplaced: list[str] = []
        for test in self._colocated_tests(src):
            text = test.read_text(encoding="utf-8", errors="replace")
            if _REAL_IO.search(text):
                misplaced.append(test.relative_to(src).as_posix())
        score = max(0, 100 - len(misplaced) * 15)
        passed = score >= PASS_THRESHOLD
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "Colocated tests are pure unit tests"
                if not misplaced
                else f"{len(misplaced)} colocated unit test(s) do real I/O"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"misplaced": misplaced[:20]},
            fix_hint=(
                "Move I/O tests to tests/integration or tests/e2e"
                if misplaced
                else None
            ),
        )

    @staticmethod
    def _colocated_tests(src: Path) -> list[Path]:
        """List ``*.test.ts``/``*.spec.ts`` files colocated in the source tree."""
        return sorted(p for p in src.rglob("*") if p.is_file() and _is_test_file(p))


# Tautological assertions: literal-truthy expectations and self-comparisons.
_TAUTOLOGY_PATTERNS = (
    re.compile(r"expect\(\s*(true|false|1|0)\s*\)"),
    re.compile(r"expect\(\s*([\w.]+)\s*\)\.toBe\(\s*\1\s*\)"),
    re.compile(r"expect\(\s*([\w.]+)\s*\)\.toEqual\(\s*\1\s*\)"),
    re.compile(r"\bassert\(\s*true\s*\)"),
)


def _all_test_files(project_path: Path) -> list[Path]:
    """List every test/spec file in the project (colocated or under tests/)."""
    roots = [project_path / "src", project_path / "tests", project_path]
    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and _is_test_file(p) and p not in seen:
                seen.add(p)
                out.append(p)
    return out


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestTautologyRule(ProjectRule):
    """Flag tautological assertions (``expect(true)``, ``x.toBe(x)``)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_TAUTOLOGY"

    def check(self, project_path: Path) -> CheckResult:
        """Count tautological assertions across the project's test files."""
        if not (project_path / "package.json").is_file():
            return _no_package_json(project_path, self.rule_id)
        hits: list[str] = []
        for test in _all_test_files(project_path):
            text = test.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if any(pat.search(line) for pat in _TAUTOLOGY_PATTERNS):
                    rel = test.relative_to(project_path).as_posix()
                    hits.append(f"{rel}:{lineno}")
        # Tautologies are zero-tolerance: any occurrence fails (like the
        # Python tautology rule), score grades severity.
        score = max(0, 100 - len(hits) * 10)
        passed = not hits
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "No tautological assertions"
                if not hits
                else f"{len(hits)} tautological assertion(s)"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"tautologies": hits[:20]},
            fix_hint="Replace weak asserts with behavioral ones" if hits else None,
        )


# A test case: it("…", () => { … }) / test("…", … ). Capture the body.
_TEST_CASE = re.compile(
    r"""\b(?:it|test)\s*\(\s*['"`].*?['"`]\s*,\s*(?:async\s*)?\(\s*\)\s*=>\s*\{"""
    r"""(?P<body>.*?)\}\s*\)\s*;?""",
    re.DOTALL,
)


# Ignore trivial bodies (e.g. a lone `expect(true).toBe(true)`) — too short to
# be a meaningful duplicate signal.
_MIN_BODY_LEN = 20


def _normalize_body(body: str) -> str:
    """Collapse whitespace so trivially-formatted-different bodies compare equal."""
    return re.sub(r"\s+", " ", body).strip()


@register_rule("test_quality", framework=Framework.NODE)
class NodeTestDuplicateRule(ProjectRule):
    """Flag duplicate test bodies (identical ``it``/``test`` blocks)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "NODE_TEST_DUPLICATE"

    def check(self, project_path: Path) -> CheckResult:
        """Count test cases whose normalized body duplicates an earlier one."""
        if not (project_path / "package.json").is_file():
            return _no_package_json(project_path, self.rule_id)
        seen: set[str] = set()
        duplicates = 0
        for test in _all_test_files(project_path):
            text = test.read_text(encoding="utf-8", errors="replace")
            for match in _TEST_CASE.finditer(text):
                body = _normalize_body(match.group("body"))
                if len(body) < _MIN_BODY_LEN:
                    continue
                if body in seen:
                    duplicates += 1
                else:
                    seen.add(body)
        # Duplicate test bodies are zero-tolerance: any duplicate fails.
        score = max(0, 100 - duplicates * 10)
        passed = duplicates == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "No duplicate test bodies"
                if not duplicates
                else f"{duplicates} duplicate test body(ies)"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"duplicate_count": duplicates},
            fix_hint="Merge or parametrize duplicate tests" if duplicates else None,
        )
