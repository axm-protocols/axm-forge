"""Text rendering for ``ast_impact`` reports."""

from __future__ import annotations

from collections.abc import Mapping

from axm_ast.core.impact import CallerEntry, DefinitionInfo, ImpactResult

__all__ = ["render_impact_batch_text", "render_impact_text"]


def _render_definition_section(defn: DefinitionInfo) -> list[str]:
    """Render the definition section lines."""
    kind = defn.get("kind", "")
    mod = defn.get("module", "?")
    ln = defn.get("line", "?")
    lines = [f"Def: {mod}:{ln} ({kind})"]
    sig = defn.get("signature")
    if sig:
        lines.append(sig)
    return lines


def _render_callers_section(callers: list[CallerEntry]) -> list[str]:
    """Render the callers section lines."""
    if not callers:
        return ["Callers: none"]
    parts = []
    for c in callers:
        name = c.get("name", "?")
        cmod = c.get("module", "?")
        cline = c.get("line")
        loc = f"{cmod}:{cline}" if cline else cmod
        parts.append(f"{name} ({loc})")
    return [f"Callers: {', '.join(parts)}"]


def _render_tests_section(test_files: list[str]) -> list[str]:
    """Render the tests section lines."""
    if not test_files:
        return ["Tests: none"]
    names = [f.rsplit("/", 1)[-1] for f in test_files]
    return [f"Tests: {', '.join(names)}"]


def _render_git_coupled_section(git_coupled: list[Mapping[str, object]]) -> list[str]:
    """Render the git-coupled section lines."""
    if not git_coupled:
        return []
    names: list[str] = []
    for entry in git_coupled:
        file_val = entry.get("file", "")
        file_str = str(file_val) if file_val else ""
        if file_str:
            names.append(file_str.rsplit("/", 1)[-1])
    if not names:
        return []
    return [f"Git-coupled: {', '.join(names)}"]


def _render_cross_package_section(
    cross: list[str] | list[Mapping[str, object]],
) -> list[str]:
    """Render the cross-package impact section lines.

    Accepts both the documented ``list[str]`` shape produced by
    ``analyze_impact`` and the legacy ``list[Mapping[str, object]]``
    shape (``{"package": ..., "module": ...}``) that older callers
    still pass.
    """
    if not cross:
        return []
    parts: list[str] = []
    for c in cross:
        if isinstance(c, Mapping):
            value = c.get("package", c.get("module", "?"))
            parts.append(str(value))
        else:
            parts.append(str(c))
    return [f"Cross-package: {', '.join(parts)}"]


def _render_impact_single(report: ImpactResult) -> str:
    """Render a single impact report dict as text."""
    symbol = report.get("symbol", "?")

    err = report.get("error")
    if err is not None:
        return f"ast_impact | {symbol} | error\n{err}"

    score = report.get("score", "UNKNOWN")
    lines: list[str] = [f"ast_impact | {symbol} | {score}"]

    defn = report.get("definition")
    if defn:
        lines.extend(_render_definition_section(defn))

    lines.extend(_render_callers_section(report.get("callers", [])))

    affected = report.get("affected_modules", [])
    if affected:
        lines.append(f"Affected: {', '.join(affected)}")

    lines.extend(_render_tests_section(report.get("test_files", [])))
    lines.extend(_render_git_coupled_section(report.get("git_coupled", [])))
    lines.extend(_render_cross_package_section(report.get("cross_package_impact", [])))

    return "\n".join(lines)


def render_impact_text(report: ImpactResult) -> str:
    """Render a single impact report as human-readable text."""
    try:
        return _render_impact_single(report)
    except (KeyError, TypeError, AttributeError):
        symbol = report.get("symbol", "?") if isinstance(report, dict) else "?"
        return f"ast_impact | {symbol} | render error"


def render_impact_batch_text(reports: list[ImpactResult]) -> str:
    """Render multiple impact reports as human-readable text."""
    if not reports:
        return ""

    try:
        score_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        best = "LOW"
        for r in reports:
            s = r.get("score", "LOW")
            if score_order.get(s, 0) > score_order.get(best, 0):
                best = s
        header = f"ast_impact | {len(reports)} symbols | max={best}"
        sections: list[str] = [header]
        for r in reports:
            symbol = r.get("symbol", "?")
            score = r.get("score", "UNKNOWN")
            section_header = f"## {symbol} | {score}"
            body = _render_impact_single(r)
            body_lines = body.split("\n")[1:]
            sections.append(section_header + "\n" + "\n".join(body_lines))
        return "\n\n".join(sections)
    except (KeyError, TypeError, AttributeError):
        return ""
