"""Verify tool — consolidated quality check with AST enrichment.

Orchestrates axm-audit + axm-init check in one shot, then enriches
failures with AST context from axm-ast (callers, impact, test files).

This module is decoupled: it receives discovered tools as a dict
and calls them via Python. No subprocess nesting.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_mcp.verify_format import format_verify_text

__all__ = ["VerifyTool", "verify_project"]

logger = logging.getLogger(__name__)

# Cap callers listed in enrichment output to keep payloads compact.
_MAX_CALLERS = 10


def verify_project(
    path: str,
    tools: Mapping[str, AXMTool],
) -> dict[str, object]:
    """One-shot project verification: audit + init check + AST enrichment.

    Args:
        path: Path to project root.
        tools: Dict of discovered tools (from ``discover_tools()``).

    Returns:
        Consolidated result with 'audit' and 'governance' sections.
        Each section is None if the corresponding tool is not installed.
    """
    audit_data = _run_tool(tools, "audit", path=path)
    governance_data = _run_tool(tools, "init_check", path=path)

    # Enrich audit failures with AST context
    if audit_data is not None:
        failed_raw = audit_data.get("failed", [])
        failed = cast(list[dict[str, object]], failed_raw) if failed_raw else []
        if failed and "ast_impact" in tools:
            for failure in failed:
                context = _enrich_failure(tools, path, failure)
                if context:
                    failure["context"] = context

    return {
        "audit": audit_data,
        "governance": governance_data,
    }


def _run_tool(
    tools: Mapping[str, AXMTool],
    tool_name: str,
    **kwargs: object,
) -> dict[str, object] | None:
    """Run a discovered tool, returning its data or None if unavailable."""
    tool = tools.get(tool_name)
    if tool is None:
        logger.info("Tool '%s' not installed, skipping.", tool_name)
        return None

    try:
        result = tool.execute(**kwargs)
        if result.success:
            data = cast(dict[str, object], result.data)
            return data
        logger.warning("Tool '%s' failed: %s", tool_name, result.error)
        return {"error": result.error}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tool '%s' raised: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc)}


def _enrich_failure(
    tools: Mapping[str, AXMTool],
    path: str,
    failure: dict[str, object],
) -> dict[str, object] | None:
    """Enrich a failure with aggregated AST context.

    Calls _extract_symbols, then ast_impact on each symbol.
    Impact scores are ordinal strings (LOW < MEDIUM < HIGH); the
    maximum across all symbols is kept.

    Returns aggregated context dict or None if no enrichment possible.
    """
    ast_tool = tools.get("ast_impact")
    if ast_tool is None:
        return None

    symbols = _extract_symbols(failure)
    if not symbols:
        return None

    # Aggregate results from all symbols
    _score_order: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    all_callers: list[dict[str, object]] = []
    all_test_files: list[str] = []
    max_score: str = "LOW"
    success_count = 0

    for symbol in symbols:
        try:
            result = ast_tool.execute(path=path, symbol=symbol)
            if result.success and result.data:
                success_count += 1
                data = cast(dict[str, object], result.data)
                callers = cast(list[dict[str, object]], data.get("callers", []))
                test_files = cast(list[str], data.get("test_files", []))
                all_callers.extend(callers)
                all_test_files.extend(test_files)
                score = cast(str, data.get("score") or "LOW")
                if _score_order.get(score, 0) > _score_order.get(max_score, 0):
                    max_score = score
        except Exception as exc:  # noqa: BLE001
            logger.warning("AST enrichment failed for %s: %s", symbol, exc)

    if success_count == 0:
        return None

    total_callers = len(all_callers)
    if total_callers > _MAX_CALLERS:
        all_callers = all_callers[:_MAX_CALLERS]
        all_callers.append(
            {
                "note": f"... and {total_callers - _MAX_CALLERS} "
                "more callers omitted for brevity"
            }
        )

    return {
        "affected_modules": list(dict.fromkeys(symbols)),
        "callers": all_callers,
        "test_files": list(dict.fromkeys(all_test_files)),
        "impact_score": max_score,
        "symbols_analyzed": success_count,
    }


def _extract_symbols(failure: dict[str, object]) -> list[str]:
    """Extract unique AST-queryable symbols from a failure dict.

    Strategy per rule_id:
    - QUALITY_TYPE: parse details.errors[].file → module path
    - QUALITY_COMPLEXITY: use details.top_offenders[].function
    - Default: fallback to message prefix parsing
    """
    rule_id = failure.get("rule_id", "")
    details = failure.get("details")

    # Strategy: mypy errors → module paths from file
    if rule_id == "QUALITY_TYPE" and isinstance(details, dict):
        errors = details.get("errors", [])
        if errors:
            return _unique_modules_from_errors(errors)

    # Strategy: complexity → function names
    if rule_id == "QUALITY_COMPLEXITY" and isinstance(details, dict):
        offenders = details.get("top_offenders", [])
        if offenders:
            return list(
                dict.fromkeys(o["function"] for o in offenders if "function" in o)
            )

    # Fallback: message prefix parsing
    message = failure.get("message", "")
    if isinstance(message, str):
        for prefix in ("Function ", "Class ", "Method "):
            if message.startswith(prefix):
                rest = message[len(prefix) :]
                parts = rest.split()
                if parts:
                    return [parts[0].strip("()'\":")]

    return []


class VerifyTool:
    """AXMTool wrapper around :func:`verify_project`.

    Returns ``ToolResult(data=..., text=...)`` so MCP consumers see a
    compact rendered report while programmatic callers (hooks, gates)
    can still read the structured ``data`` dict.
    """

    agent_hint = (
        "One-shot project verification: audit + init check + AST enrichment. "
        "Returns compact text plus structured data."
    )

    def __init__(self, tools: Mapping[str, object] | None = None) -> None:
        # The discovery layer hands us a ``Mapping[str, ToolEntry]`` (structural
        # protocols), but every entry-point-registered tool is in fact an
        # ``AXMTool`` instance. We accept ``object`` at the boundary so
        # ``mcp_app.py`` stays decoupled from ``axm.*`` core, then trust the
        # runtime invariant via a cast.
        self._tools: Mapping[str, AXMTool] = cast(
            "Mapping[str, AXMTool]", tools if tools is not None else {}
        )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "verify"

    def execute(self, *, path: str = ".", **_: object) -> ToolResult:
        """One-shot project verification: audit + init check + AST enrichment.

        Args:
            path: Path to project root to verify.
        """
        data = verify_project(str(path), self._tools)
        text = format_verify_text(data)
        return ToolResult(success=True, data=data, text=text)


def _unique_modules_from_errors(errors: list[dict[str, object]]) -> list[str]:
    """Convert file paths to unique module paths.

    'src/foo/bar.py' → 'foo.bar'
    'tests/test_main.py' → 'tests.test_main'
    """
    modules: list[str] = []
    seen: set[str] = set()

    for entry in errors:
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path:
            continue

        # Strip src/ prefix if present
        path = file_path
        if path.startswith("src/"):
            path = path[4:]

        # Convert to module path: strip .py, replace /
        if path.endswith(".py"):
            path = path[:-3]
        module = path.replace("/", ".")

        if module not in seen:
            seen.add(module)
            modules.append(module)

    return modules
