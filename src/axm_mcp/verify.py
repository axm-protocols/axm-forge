"""Verify tool — consolidated quality check with AST enrichment.

Orchestrates axm-audit + axm-init check in one shot, then enriches
failures with AST context from axm-ast (callers, impact, test files).

This module is decoupled: it receives discovered tools as a dict
and calls them via Python. No subprocess nesting.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["verify_project"]

logger = logging.getLogger(__name__)


def verify_project(
    path: str,
    tools: dict[str, Any],
) -> dict[str, Any]:
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
        failed = audit_data.get("failed", [])
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
    tools: dict[str, Any],
    tool_name: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Run a discovered tool, returning its data or None if unavailable."""
    tool = tools.get(tool_name)
    if tool is None:
        logger.info("Tool '%s' not installed, skipping.", tool_name)
        return None

    try:
        result = tool.execute(**kwargs)
        if result.success:
            data: dict[str, Any] = result.data
            return data
        logger.warning("Tool '%s' failed: %s", tool_name, result.error)
        return {"error": result.error}
    except Exception as exc:
        logger.warning("Tool '%s' raised: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc)}


def _enrich_failure(
    tools: dict[str, Any],
    path: str,
    failure: dict[str, Any],
) -> dict[str, Any] | None:
    """Enrich a failure with aggregated AST context.

    Calls _extract_symbols, then ast_impact on each.
    Returns aggregated context or None if no enrichment possible.
    """
    ast_tool = tools.get("ast_impact")
    if ast_tool is None:
        return None

    symbols = _extract_symbols(failure)
    if not symbols:
        return None

    # Aggregate results from all symbols
    all_callers: list[dict[str, Any]] = []
    all_test_files: list[str] = []
    max_score: float = 0.0
    success_count = 0

    for symbol in symbols:
        try:
            result = ast_tool.execute(path=path, symbol=symbol)
            if result.success and result.data:
                success_count += 1
                all_callers.extend(result.data.get("callers", []))
                all_test_files.extend(result.data.get("test_files", []))
                score = result.data.get("score", 0)
                if score > max_score:
                    max_score = score
        except Exception as exc:
            logger.debug("AST enrichment failed for %s: %s", symbol, exc)

    if success_count == 0:
        return None

    return {
        "affected_modules": list(dict.fromkeys(symbols)),
        "callers": all_callers,
        "test_files": list(dict.fromkeys(all_test_files)),
        "impact_score": max_score,
        "symbols_analyzed": success_count,
    }


def _extract_symbols(failure: dict[str, Any]) -> list[str]:
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
    for prefix in ("Function ", "Class ", "Method "):
        if message.startswith(prefix):
            rest = message[len(prefix) :]
            parts = rest.split()
            if parts:
                return [parts[0].strip("()'\":")]

    return []


def _unique_modules_from_errors(errors: list[dict[str, Any]]) -> list[str]:
    """Convert file paths to unique module paths.

    'src/foo/bar.py' → 'foo.bar'
    'tests/test_main.py' → 'tests.test_main'
    """
    modules: list[str] = []
    seen: set[str] = set()

    for entry in errors:
        file_path = entry.get("file")
        if not file_path:
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
