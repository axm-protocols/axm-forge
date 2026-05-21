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


def format_report(r: PipelineReport, project_path: Path) -> str:
    lines: list[str] = []
    head = "applied" if r.applied else "dry-run"
    iter_suffix = f" — {r.iterations} iteration(s)" if r.applied else ""
    lines.append(f"\nPipeline ({head}{iter_suffix}) on {project_path}")
    lines.append("=" * 78)
    counts = r.by_kind()
    total = sum(counts.values())
    if not total:
        lines.append("  (no deterministic ops planned)")
    else:
        for kind in ("flatten", "relocate", "split", "merge", "rename"):
            n = counts.get(kind, 0)
            if n:
                lines.append(f"  Stage {kind.upper():9s} {n} op(s)")
    if r.ops:
        lines.append("")
        lines.append("Details (first 30):")
        for op in r.ops[:30]:
            try:
                src = op.source.relative_to(project_path)
            except ValueError:
                src = op.source
            lines.append(f"  [{op.kind:8s}] {src}")
            lines.append(f"               -> {_fmt_target(op.target, project_path)}")
            lines.append(f"               rationale: {op.rationale}")
        if len(r.ops) > 30:
            lines.append(f"  ... +{len(r.ops) - 30} more")
    lines.append("")
    if r.unfixable:
        lines.append(f"Out of pipeline (agent-driven, {len(r.unfixable)} finding(s)):")
        for u in r.unfixable[:20]:
            tf = u.get("test_file") or u.get("path") or "?"
            lines.append(f"  {u['rule_id']}: {tf}")
        if len(r.unfixable) > 20:
            lines.append(f"  ... +{len(r.unfixable) - 20} more")
        lines.append(
            "  -> Run /scenario-rename or inspect manually — these tests "
            "may be legitimate or candidates for deletion."
        )
    else:
        lines.append("Out of pipeline: 0 finding")
    if r.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(r.warnings)}):")
        for w in r.warnings[:15]:
            lines.append(f"  ! {w}")
        if len(r.warnings) > 15:
            lines.append(f"  ... +{len(r.warnings) - 15} more")
    return "\n".join(lines)
