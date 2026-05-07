"""Text rendering for ``ast_impact`` reports."""

from __future__ import annotations

from typing import Any

__all__ = ["render_impact_batch_text", "render_impact_text"]


def _render_definition_section(defn: dict[str, Any]) -> list[str]:
    """Render the definition section lines."""
    kind = defn.get("kind", "")
    mod = defn.get("module", "?")
    ln = defn.get("line", "?")
    lines = [f"Def: {mod}:{ln} ({kind})"]
    sig = defn.get("signature")
    if sig:
        lines.append(sig)
    return lines


def _render_callers_section(callers: list[dict[str, Any]]) -> list[str]:
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


def _render_git_coupled_section(git_coupled: list[str]) -> list[str]:
    """Render the git-coupled section lines."""
    if not git_coupled:
        return []
    names = [f.rsplit("/", 1)[-1] for f in git_coupled]
    return [f"Git-coupled: {', '.join(names)}"]


def _render_cross_package_section(cross: list[Any]) -> list[str]:
    """Render the cross-package impact section lines."""
    if not cross:
        return []
    pkgs = ", ".join(
        str(c.get("package", c.get("module", "?"))) if isinstance(c, dict) else str(c)
        for c in cross
    )
    return [f"Cross-package: {pkgs}"]


def _render_impact_single(report: dict[str, Any]) -> str:
    """Render a single impact report dict as text."""
    symbol = report.get("symbol", "?")

    if "error" in report:
        return f"ast_impact | {symbol} | error\n{report['error']}"

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


def render_impact_text(report: dict[str, Any]) -> str:
    """Render a single impact report as human-readable text."""
    try:
        return _render_impact_single(report)
    except (KeyError, TypeError, AttributeError):
        symbol = report.get("symbol", "?") if isinstance(report, dict) else "?"
        return f"ast_impact | {symbol} | render error"


def render_impact_batch_text(reports: list[dict[str, Any]]) -> str:
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
