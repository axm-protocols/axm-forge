"""Complexity rule — cyclomatic + cognitive complexity analysis."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import (
    PASS_THRESHOLD,
    ProjectRule,
    register_rule,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["ComplexityRule"]

_HIGH_COMPLEXITY_RANKS: frozenset[str] = frozenset({"C", "D", "E", "F"})
_COGNITIVE_THRESHOLD = 15

logger = logging.getLogger(__name__)


@dataclass
@register_rule("complexity")
class ComplexityRule(ProjectRule):
    """Analyse complexity via radon (CC) and complexipy (Cognitive).

    Double constraint: a function is flagged if either radon grade is
    C+ (CC >= 11, aligned with ruff C901) or cognitive complexity > 15
    (SonarSource convention: strictly higher than 15, aligned with
    complexipy). A function exceeding both thresholds counts
    as one violation (no double penalty) but is reported with
    ``reason='cc+cog'``. Falls back gracefully to CC-only mode when
    complexipy is unavailable.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_COMPLEXITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check project complexity with radon + complexipy."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        cog_map, cog_disabled = _compute_cognitive_map(src_path)

        radon_api = _try_import_radon()
        if radon_api is not None:
            cc_visit, cc_rank = radon_api
            return self._check_via_api(
                src_path, cc_visit, cc_rank, cog_map, cog_disabled
            )

        return self._check_via_subprocess(src_path, cog_map, cog_disabled)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_via_api(
        self,
        src_path: Path,
        cc_visit: Callable[..., list[Any]],
        cc_rank: Callable[[int], str],
        cog_map: dict[tuple[str, str], int],
        cog_disabled: bool,
    ) -> CheckResult:
        """Analyse complexity using the radon Python API."""
        offenders: list[dict[str, str | int]] = []
        for py_file in src_path.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                blocks = cc_visit(source)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for block in blocks:
                if not hasattr(block, "complexity"):
                    continue
                cc = int(block.complexity)
                rank = cc_rank(cc)
                classname = getattr(block, "classname", "") or ""
                name = f"{classname}.{block.name}" if classname else block.name
                cognitive = cog_map.get((py_file.name, name), 0)
                offender = _classify(py_file.name, name, cc, rank, cognitive)
                if offender is not None:
                    offenders.append(offender)
        return self._build_result(offenders, cog_disabled)

    def _check_via_subprocess(
        self,
        src_path: Path,
        cog_map: dict[tuple[str, str], int],
        cog_disabled: bool,
    ) -> CheckResult:
        """Analyse complexity by shelling out to ``radon cc --json``."""
        radon_bin = shutil.which("radon")
        if radon_bin is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=("radon not found — complexity analysis skipped"),
                severity=Severity.ERROR,
                details={"score": 0},
                fix_hint=(
                    "Run 'uv sync' at workspace root or "
                    "'uv pip install axm-audit' to make radon available"
                ),
            )

        try:
            proc = subprocess.run(  # noqa: S603
                [radon_bin, "cc", "--json", str(src_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            data: dict[str, list[dict[str, object]]] = (
                json.loads(proc.stdout) if proc.stdout.strip() else {}
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "radon cc --json failed: %s",
                exc,
                exc_info=True,
            )
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="radon cc --json failed",
                severity=Severity.ERROR,
                details={"score": 0},
                fix_hint="Check radon installation",
            )

        return self._process_radon_output(data, cog_map, cog_disabled)

    def _process_radon_output(
        self,
        data: dict[str, list[dict[str, object]]],
        cog_map: dict[tuple[str, str], int] | None = None,
        cog_disabled: bool = False,
    ) -> CheckResult:
        """Process JSON output from radon cc."""
        if cog_map is None:
            cog_map = {}
        offenders: list[dict[str, str | int]] = []
        for file_path, blocks in data.items():
            file_name = Path(file_path).name
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                rank = str(block.get("rank", ""))
                raw_cc = block.get("complexity", 0)
                cc = int(raw_cc) if isinstance(raw_cc, int | float | str) else 0
                raw_name = str(block.get("name", ""))
                classname = str(block.get("classname", ""))
                name = f"{classname}.{raw_name}" if classname else raw_name
                cognitive = cog_map.get((file_name, name), 0)
                offender = _classify(file_name, name, cc, rank, cognitive)
                if offender is not None:
                    offenders.append(offender)
        return self._build_result(offenders, cog_disabled)

    def _build_result(
        self,
        offenders: list[dict[str, str | int]],
        cog_disabled: bool = False,
    ) -> CheckResult:
        """Build the final ``CheckResult`` from computed metrics."""
        top_offenders = sorted(
            offenders,
            key=lambda x: max(int(x["cc"]), int(x.get("cognitive", 0))),
            reverse=True,
        )
        high_complexity_count = len(top_offenders)
        score = max(0, 100 - high_complexity_count * 10)
        passed = score >= PASS_THRESHOLD

        text_lines = [
            (
                f"• {o['file']}:{o['function']} "
                f"cc={o['cc']} ({o['rank']}) cog={o['cognitive']} [{o['reason']}]"
            )
            for o in top_offenders
        ]

        message = (
            f"Complexity score: {score}/100 "
            f"({high_complexity_count} high-complexity functions)"
        )
        if cog_disabled:
            message += " — cognitive layer disabled (complexipy unavailable)"

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=(
                Severity.WARNING if not passed or cog_disabled else Severity.INFO
            ),
            details={
                "high_complexity_count": high_complexity_count,
                "top_offenders": top_offenders,
                "score": score,
                "cognitive_disabled": cog_disabled,
            },
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=(
                "Refactor complex functions into smaller units"
                if high_complexity_count > 0
                else None
            ),
        )


def _try_import_radon() -> tuple[Callable[..., list[Any]], Callable[[int], str]] | None:
    """Try to import radon's ``cc_visit`` and ``cc_rank``.

    Returns:
        ``(cc_visit, cc_rank)`` callables, or ``None`` if radon is not available.
    """
    try:
        from radon.complexity import cc_rank, cc_visit

        return cc_visit, cc_rank
    except ModuleNotFoundError:
        return None


def _try_import_complexipy() -> Callable[..., Any] | None:
    """Try to import complexipy's ``file_complexity``.

    Returns:
        The ``file_complexity`` callable, or ``None`` if complexipy is missing.
    """
    try:
        from complexipy import file_complexity

        return file_complexity
    except ModuleNotFoundError:
        return None


def _classify(
    file_name: str, function: str, cc: int, rank: str, cognitive: int
) -> dict[str, str | int] | None:
    """Classify a function. Return offender dict if it violates, else None."""
    cc_violates = rank in _HIGH_COMPLEXITY_RANKS
    cog_violates = cognitive > _COGNITIVE_THRESHOLD
    if not (cc_violates or cog_violates):
        return None
    if cc_violates and cog_violates:
        reason = "cc+cog"
    elif cc_violates:
        reason = "cc"
    else:
        reason = "cog"
    return {
        "file": file_name,
        "function": function,
        "cc": cc,
        "rank": rank,
        "cognitive": cognitive,
        "reason": reason,
    }


def _compute_cognitive_map(
    src_path: Path,
) -> tuple[dict[tuple[str, str], int], bool]:
    """Compute (file, function) -> cognitive score map.

    Returns ``(map, disabled)``. ``disabled=True`` means complexipy is
    unavailable (neither importable nor on PATH); the map is empty
    and callers should fall back to CC-only mode.
    """
    api = _try_import_complexipy()
    if api is not None:
        return _cognitive_via_api(src_path, api), False
    via_subprocess = _cognitive_via_subprocess(src_path)
    if via_subprocess is None:
        return {}, True
    return via_subprocess, False


def _cognitive_via_api(
    src_path: Path, file_complexity: Callable[..., Any]
) -> dict[tuple[str, str], int]:
    """Compute cognitive scores via complexipy Python API."""
    result: dict[tuple[str, str], int] = {}
    for py_file in src_path.rglob("*.py"):
        try:
            fc = file_complexity(str(py_file))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as exc:
            logger.debug("complexipy file_complexity failed for %s: %s", py_file, exc)
            continue
        for fn in getattr(fc, "functions", []) or []:
            name = getattr(fn, "name", "") or getattr(fn, "function_name", "")
            score = int(getattr(fn, "complexity", 0) or 0)
            if name:
                result[(py_file.name, name)] = score
    return result


def _cognitive_via_subprocess(
    src_path: Path,
) -> dict[tuple[str, str], int] | None:
    """Compute cognitive scores via ``complexipy`` subprocess.

    Returns ``None`` when the binary is not available.
    """
    binary = shutil.which("complexipy")
    if binary is None:
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            subprocess.run(  # noqa: S603
                [binary, str(src_path), "--output-format", "json", "--quiet"],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmpdir,
            )
        except OSError as exc:
            logger.warning("complexipy subprocess failed: %s", exc, exc_info=True)
            return {}
        report = Path(tmpdir) / "complexipy-results.json"
        if not report.exists():
            return {}
        try:
            entries = json.loads(report.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("complexipy JSON parse failed: %s", exc, exc_info=True)
            return {}
    return _parse_complexipy_entries(entries)


def _parse_complexipy_entries(entries: object) -> dict[tuple[str, str], int]:
    """Parse complexipy JSON entries into a ``(file, function) -> score`` map."""
    result: dict[tuple[str, str], int] = {}
    if not isinstance(entries, list):
        return result
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        file_name = str(entry.get("file_name", ""))
        function = str(entry.get("function_name", ""))
        score = entry.get("complexity", 0)
        if file_name and function and isinstance(score, int | float):
            result[(file_name, function)] = int(score)
    return result
