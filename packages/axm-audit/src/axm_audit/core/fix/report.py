"""Human-readable report formatting (CLI output)."""

from __future__ import annotations

from pathlib import Path

from .models import PipelineReport

__all__ = ["format_report"]


def _fmt_target(t: Path | list[Path], root: Path) -> str:
    if isinstance(t, Path):
        try:
            return str(t.relative_to(root))
        except ValueError:
            return str(t)
    return ", ".join(_fmt_target(x, root) for x in t)


_STAGE_ORDER = ("flatten", "relocate", "split", "merge", "rename")


def _fmt_header(r: PipelineReport, project_path: Path) -> list[str]:
    head = "applied" if r.applied else "dry-run"
    iter_suffix = f" — {r.iterations} iteration(s)" if r.applied else ""
    return [f"\nPipeline ({head}{iter_suffix}) on {project_path}", "=" * 78]


def _fmt_counts(r: PipelineReport) -> list[str]:
    counts = r.by_kind()
    if not sum(counts.values()):
        return ["  (no deterministic ops planned)"]
    out: list[str] = []
    for kind in _STAGE_ORDER:
        n = counts.get(kind, 0)
        if n:
            out.append(f"  Stage {kind.upper():9s} {n} op(s)")
    return out


def _fmt_ops(r: PipelineReport, project_path: Path) -> list[str]:
    if not r.ops:
        return []
    out: list[str] = ["", "Details (first 30):"]
    for op in r.ops[:30]:
        try:
            src = op.source.relative_to(project_path)
        except ValueError:
            src = op.source
        out.append(f"  [{op.kind:8s}] {src}")
        out.append(f"               -> {_fmt_target(op.target, project_path)}")
        out.append(f"               rationale: {op.rationale}")
    if len(r.ops) > 30:
        out.append(f"  ... +{len(r.ops) - 30} more")
    return out


def _fmt_unfixable(r: PipelineReport) -> list[str]:
    if not r.unfixable:
        return ["Out of pipeline: 0 finding"]
    out: list[str] = [f"Out of pipeline (agent-driven, {len(r.unfixable)} finding(s)):"]
    for u in r.unfixable[:20]:
        tf = u.get("test_file") or u.get("path") or "?"
        out.append(f"  {u['rule_id']}: {tf}")
    if len(r.unfixable) > 20:
        out.append(f"  ... +{len(r.unfixable) - 20} more")
    out.append(
        "  -> Run /scenario-rename or inspect manually — these tests "
        "may be legitimate or candidates for deletion."
    )
    return out


def _fmt_warnings(r: PipelineReport) -> list[str]:
    if not r.warnings:
        return []
    out: list[str] = ["", f"Warnings ({len(r.warnings)}):"]
    for w in r.warnings[:15]:
        out.append(f"  ! {w}")
    if len(r.warnings) > 15:
        out.append(f"  ... +{len(r.warnings) - 15} more")
    return out


def format_report(r: PipelineReport, project_path: Path) -> str:
    lines: list[str] = []
    lines.extend(_fmt_header(r, project_path))
    lines.extend(_fmt_counts(r))
    lines.extend(_fmt_ops(r, project_path))
    lines.append("")
    lines.extend(_fmt_unfixable(r))
    lines.extend(_fmt_warnings(r))
    return "\n".join(lines)
