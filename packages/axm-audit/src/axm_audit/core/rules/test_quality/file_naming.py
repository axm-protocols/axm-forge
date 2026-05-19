"""TEST_QUALITY_FILE_NAMING rule.

For every integration / e2e test file, derive the canonical ``test_*.py``
filename from the top-K=2 tuple of (first-party symbols | CLI invocations)
and compare with the current basename. Three verdicts:

* ``NAME_MISMATCH`` (INFO) — the file uses a name that diverges from the
  canonical tuple. Surfaced as signal, not as a defect: cohesive packages
  often pick human scenario names that beat the canonical tuple.
* ``SPLIT`` (WARNING) — the file holds tests that map to multiple distinct
  canonical tuples. A structural problem of the file boundary, regardless
  of the chosen name.
* ``COLLIDE`` (WARNING) — two or more files in the same tier emit the same
  canonical name. Same structural-boundary problem viewed in the other
  direction.

The rule auto-skips ``tests/unit/`` (handled by ``PRACTICE_TEST_MIRROR``)
and respects a file-level / per-test ``pytest.mark.scenario_name_ok``
marker that suppresses NAME_MISMATCH (only).
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality._shared import (
    _parse_cached,
    canonical_filename,
    cli_invocation_tuple,
    current_level_from_path,
    file_has_module_marker,
    first_party_symbol_counts,
    get_pkg_prefixes,
    iter_test_files,
    iter_test_funcs,
    load_project_scripts,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["FileNamingRule", "compute_canonical_name"]

_TOP_K = 2
_MARKER_NAME = "scenario_name_ok"
_INFO_PENALTY = 1
_WARNING_PENALTY = 3
_MIN_DISTINCT_FOR_SPLIT = 2
_MIN_FILES_FOR_COLLIDE = 2
_MAX_TEXT_WARNINGS = 10
_MAX_TEXT_INFOS = 5


@dataclass(frozen=True)
class _ScanContext:
    project_path: Path
    pkg_prefixes: set[str]
    project_scripts: set[str]
    single_binary: str | None


@dataclass
class _FileVerdict:
    test_file: Path
    tier: str
    canonical: str
    per_test_tuples: list[tuple[str, ...]] = field(default_factory=list)
    file_marked: bool = False

    @property
    def current_name(self) -> str:
        return self.test_file.name

    @property
    def distinct_non_empty_tuples(self) -> set[tuple[str, ...]]:
        return {t for t in self.per_test_tuples if t}

    @property
    def is_split(self) -> bool:
        return len(self.distinct_non_empty_tuples) > 1

    @property
    def has_canonical(self) -> bool:
        return bool(self.canonical) and self.canonical != "test_UNKNOWN.py"


@dataclass(frozen=True)
class Finding:
    verdict: str
    severity: Severity
    tier: str
    current_name: str
    proposed_name: str
    path: str
    tuple_tokens: tuple[str, ...] = ()
    tuples: tuple[tuple[str, ...], ...] = ()
    suggested_splits: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    canonical_name: str = ""

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "verdict": self.verdict,
            "severity": self.severity.value,
            "tier": self.tier,
            "current_name": self.current_name,
            "proposed_name": self.proposed_name,
            "path": self.path,
        }
        if self.verdict == "NAME_MISMATCH":
            payload["tuple"] = list(self.tuple_tokens)
        elif self.verdict == "SPLIT":
            payload["tuples"] = [list(t) for t in self.tuples]
            payload["suggested_splits"] = list(self.suggested_splits)
        elif self.verdict == "COLLIDE":
            payload["canonical_name"] = self.canonical_name
            payload["files"] = list(self.files)
        return payload


def _per_test_symbols(
    func: ast.FunctionDef, tree: ast.Module, ctx: _ScanContext
) -> tuple[str, ...]:
    counts: Counter[str] = first_party_symbol_counts(
        test_func=func, mod_ast=tree, pkg_prefixes=ctx.pkg_prefixes
    )
    ranked = [sym for sym, _ in counts.most_common()]
    return tuple(sorted(ranked[:_TOP_K]))


def _per_test_cli_tuples(
    func: ast.FunctionDef, tree: ast.Module, ctx: _ScanContext
) -> tuple[tuple[str, str], ...]:
    counts: Counter[tuple[str, str]] = cli_invocation_tuple(
        test_func=func, mod_ast=tree, project_scripts=ctx.project_scripts
    )
    ranked = [tup for tup, _ in counts.most_common()]
    return tuple(ranked[:_TOP_K])


def _canonical_for_tuple(tier: str, tup: object, ctx: _ScanContext) -> str:
    return canonical_filename(
        symbols_or_tuples=tup,
        tier=tier,
        single_binary=ctx.single_binary if tier == "e2e" else None,
    )


def _aggregate_file(
    test_file: Path,
    tree: ast.Module,
    tier: str,
    ctx: _ScanContext,
) -> _FileVerdict | None:
    file_marked = file_has_module_marker(tree, _MARKER_NAME)
    per_test: list[tuple[str, ...]] = []
    agg_symbols: Counter[str] = Counter()
    agg_cli: Counter[tuple[str, str]] = Counter()
    saw_test = False
    for func in iter_test_funcs(tree):
        saw_test = True
        if tier == "e2e":
            cli_tup = _per_test_cli_tuples(func, tree, ctx)
            per_test.append(cli_tup)  # type: ignore[arg-type]
            for tup in cli_tup:
                agg_cli[tup] += 1
        else:
            sym_tup = _per_test_symbols(func, tree, ctx)
            per_test.append(sym_tup)
            for sym in sym_tup:
                agg_symbols[sym] += 1
    if not saw_test:
        return None
    if tier == "e2e":
        e2e_union: tuple[tuple[str, str], ...] = tuple(
            tup for tup, _ in agg_cli.most_common(_TOP_K)
        )
        canonical = _canonical_for_tuple(tier, e2e_union, ctx)
    else:
        ranked = [s for s, _ in agg_symbols.most_common()]
        sym_union: tuple[str, ...] = tuple(sorted(ranked[:_TOP_K]))
        canonical = _canonical_for_tuple(tier, sym_union, ctx)
    return _FileVerdict(
        test_file=test_file,
        tier=tier,
        canonical=canonical,
        per_test_tuples=per_test,
        file_marked=file_marked,
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _mismatch_finding(verdict_data: _FileVerdict, root: Path) -> Finding | None:
    if verdict_data.file_marked:
        return None
    if verdict_data.current_name == verdict_data.canonical:
        return None
    if not verdict_data.has_canonical:
        return None
    tokens = tuple(
        sorted(
            {t for tup in verdict_data.distinct_non_empty_tuples for t in _flatten(tup)}
        )
    )
    return Finding(
        verdict="NAME_MISMATCH",
        severity=Severity.INFO,
        tier=verdict_data.tier,
        current_name=verdict_data.current_name,
        proposed_name=verdict_data.canonical,
        path=_rel(verdict_data.test_file, root),
        tuple_tokens=tokens,
    )


def _flatten(tup: tuple) -> tuple[str, ...]:  # type: ignore[type-arg]
    """Flatten a tuple of symbols or (bin, sub) pairs to a flat str tuple."""
    out: list[str] = []
    for item in tup:
        if isinstance(item, tuple):
            out.extend(s for s in item if s)
        elif isinstance(item, str) and item:
            out.append(item)
    return tuple(out)


def _split_finding(
    verdict_data: _FileVerdict, root: Path, ctx: _ScanContext
) -> Finding | None:
    distinct = verdict_data.distinct_non_empty_tuples
    if len(distinct) <= 1:
        return None
    suggestions = sorted(
        {_canonical_for_tuple(verdict_data.tier, t, ctx) for t in distinct}
    )
    suggestions = [s for s in suggestions if s != "test_UNKNOWN.py"]
    if len(suggestions) < _MIN_DISTINCT_FOR_SPLIT:
        return None
    return Finding(
        verdict="SPLIT",
        severity=Severity.WARNING,
        tier=verdict_data.tier,
        current_name=verdict_data.current_name,
        proposed_name=verdict_data.canonical,
        path=_rel(verdict_data.test_file, root),
        tuples=tuple(sorted(distinct)),
        suggested_splits=tuple(suggestions),
    )


def _collide_findings(verdicts: list[_FileVerdict], root: Path) -> list[Finding]:
    by_tier: dict[tuple[str, str], list[_FileVerdict]] = {}
    for v in verdicts:
        if not v.has_canonical:
            continue
        by_tier.setdefault((v.tier, v.canonical), []).append(v)
    findings: list[Finding] = []
    for (tier, canonical), group in by_tier.items():
        if len(group) < _MIN_FILES_FOR_COLLIDE:
            continue
        files = tuple(sorted(_rel(v.test_file, root) for v in group))
        findings.append(
            Finding(
                verdict="COLLIDE",
                severity=Severity.WARNING,
                tier=tier,
                current_name="",
                proposed_name=canonical,
                path="",
                canonical_name=canonical,
                files=files,
            )
        )
    return findings


def _build_scan_context(project_path: Path) -> _ScanContext:
    project_scripts = load_project_scripts(project_path)
    return _ScanContext(
        project_path=project_path,
        pkg_prefixes=get_pkg_prefixes(project_path),
        project_scripts=project_scripts,
        single_binary=(
            next(iter(project_scripts)) if len(project_scripts) == 1 else None
        ),
    )


def _verdict_for_file(
    test_file: Path, project_path: Path, ctx: _ScanContext | None = None
) -> _FileVerdict | None:
    """Single-file pipeline used by both ``FileNamingRule`` and the
    public ``compute_canonical_name`` helper.

    Returns ``None`` when the file is not in an integration/e2e tier,
    cannot be parsed, has no test functions, or has no first-party
    symbol coverage (canonical resolves to ``test_UNKNOWN.py``).
    """
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        return None
    tier = current_level_from_path(test_file, tests_dir)
    if tier not in {"integration", "e2e"}:
        return None
    tree = _parse_cached(test_file)
    if tree is None:
        return None
    scan_ctx = ctx if ctx is not None else _build_scan_context(project_path)
    verdict = _aggregate_file(test_file, tree, tier, scan_ctx)
    if verdict is None or not verdict.has_canonical:
        return None
    return verdict


def compute_canonical_name(test_file: Path, project_path: Path) -> str | None:
    """Public canonical-name helper for one integration/e2e test file.

    Returns ``None`` when the file is not in an integration/e2e tier,
    has no tests, or has no first-party symbol coverage. Otherwise
    returns the canonical ``test_*.py`` basename FILE_NAMING would emit.
    """
    verdict = _verdict_for_file(test_file, project_path)
    return verdict.canonical if verdict is not None else None


@register_rule(category="test_quality")
class FileNamingRule(ProjectRule):
    """Surface integration / e2e test files whose name diverges from the
    canonical tuple, or whose tests structurally belong in several files.
    """

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_FILE_NAMING"

    def check(self, project_path: Path) -> CheckResult:
        """Scan integration/e2e tests and emit naming findings."""
        early = self.check_src(project_path)
        if early is not None:
            return early
        tests_dir = project_path / "tests"
        if not tests_dir.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="no tests/ directory",
                severity=Severity.INFO,
                score=100,
            )
        ctx = _build_scan_context(project_path)
        verdicts: list[_FileVerdict] = []
        for test_file, tree in iter_test_files(project_path):
            if tree is None:
                continue
            tier = current_level_from_path(test_file, tests_dir)
            if tier not in {"integration", "e2e"}:
                continue
            verdict = _aggregate_file(test_file, tree, tier, ctx)
            if verdict is not None:
                verdicts.append(verdict)
        findings = self._collect_findings(verdicts, project_path, ctx)
        return self._build_check_result(findings)

    @staticmethod
    def _collect_findings(
        verdicts: list[_FileVerdict], root: Path, ctx: _ScanContext
    ) -> list[Finding]:
        out: list[Finding] = []
        for v in verdicts:
            mismatch = _mismatch_finding(v, root)
            if mismatch is not None:
                out.append(mismatch)
            split = _split_finding(v, root, ctx)
            if split is not None:
                out.append(split)
        out.extend(_collide_findings(verdicts, root))
        return out

    def _build_check_result(self, findings: list[Finding]) -> CheckResult:
        n_info = sum(1 for f in findings if f.severity == Severity.INFO)
        n_warning = sum(1 for f in findings if f.severity == Severity.WARNING)
        score = max(0, 100 - _INFO_PENALTY * n_info - _WARNING_PENALTY * n_warning)
        passed = n_warning == 0
        message = (
            f"{len(findings)} naming finding(s): {n_info} INFO + {n_warning} WARNING"
            if findings
            else "every integration/e2e file matches its canonical tuple"
        )
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING if n_warning else Severity.INFO,
            score=score,
            details={"findings": [f.as_dict() for f in findings]},
            text=render_findings_text(findings),
        )


def render_findings_text(findings: list[Finding]) -> str | None:
    """Render top-N findings as a compact bullet list.

    Caps at ``_MAX_TEXT_WARNINGS`` warnings + ``_MAX_TEXT_INFOS`` infos.
    Returns ``None`` for empty input, matching the convention used by
    ``render_clusters_text`` for the passing case.
    """
    if not findings:
        return None
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    infos = [f for f in findings if f.severity == Severity.INFO]
    shown_warnings = warnings[:_MAX_TEXT_WARNINGS]
    shown_infos = infos[:_MAX_TEXT_INFOS]
    lines = [
        f"• [{f.severity.name}] {f.path} → {f.proposed_name}"
        for f in (*shown_warnings, *shown_infos)
    ]
    truncated_warnings = len(warnings) - len(shown_warnings)
    truncated_infos = len(infos) - len(shown_infos)
    extra = truncated_warnings + truncated_infos
    if extra:
        lines.append(
            f"(+{extra} more findings: "
            f"{truncated_warnings} WARNING, {truncated_infos} INFO)"
        )
    return "\n".join(lines)
