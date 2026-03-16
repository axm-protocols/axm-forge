"""TraceSourceHook — enriched BFS trace with function source code.

Protocol hook that calls ``trace_flow(detail="source")`` and returns
the complete trace as ``HookResult`` metadata.  Registered as
``ast:trace-source`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["TraceSourceHook", "_parse_entry", "_resolve_scope"]

# Lazy imports — avoid importing heavy tree-sitter at module level
analyze_package: Any = None
trace_flow: Any = None

# SWE-bench format: "test_name (module.path.ClassName)"
_SWE_RE = re.compile(r"^([\w.]+)\s*\(([^)]+)\)")


def _parse_entry(entry: str) -> tuple[str, str | None]:
    """Parse a test entry string into (symbol_name, test_dir).

    Supports three formats:

    1. **SWE-bench**: ``"test_name (module.path.ClassName)"``
       → ``("test_name", "module")``  (first dotted component)
    2. **Pytest**: ``"tests/path/file.py::Class::method"``
       → ``("method", "tests/path")``  (directory of the test file)
    3. **Simple symbol**: ``"HttpResponse"``
       → ``("HttpResponse", None)``

    Args:
        entry: Raw entry string from protocol params. (Can be comma-separated list,
              in which case only the first item is traced.)

    Returns:
        Tuple of (symbol_name, test_dir_relative_or_None).
    """
    entry = entry.strip()

    # If multiple tests are provided (comma-separated), trace the first one
    if "," in entry:
        entry = entry.split(",")[0].strip()

    # 1. SWE-bench format
    m = _SWE_RE.match(entry)
    if m:
        test_name = m.group(1)
        module_path = m.group(2)  # e.g. "httpwrappers.tests.HttpResponseTests"
        # First component = test app directory
        test_dir = module_path.split(".")[0]
        return test_name, test_dir

    # 2. Pytest format (contains ::)
    if "::" in entry:
        file_part, *symbol_parts = entry.split("::")
        symbol_name = symbol_parts[-1] if symbol_parts else file_part
        # Directory of the test file
        test_dir = str(Path(file_part).parent)
        return symbol_name, test_dir

    # 3. Simple symbol
    return entry, None


def _resolve_scope(base_path: Path, test_dir: str | None) -> Path:
    """Resolve the analysis scope directory.

    Args:
        base_path: Repository root or explicit path param.
        test_dir: Relative test directory from ``_parse_entry``,
            or ``None`` for simple symbols.

    Returns:
        Absolute path to the directory to analyze.
        Falls back to *base_path* if scoped dir doesn't exist.
    """
    if test_dir is None:
        return base_path

    # If test_dir already starts with "tests/", use it directly
    if test_dir.startswith("tests/") or test_dir.startswith("tests\\"):
        scoped = base_path / test_dir
    else:
        scoped = base_path / "tests" / test_dir

    return scoped if scoped.is_dir() else base_path


@dataclass
class TraceSourceHook:
    """Run ``trace_flow(detail="source")`` and return the enriched trace.

    Reads ``working_dir`` from *context* and ``entry`` from *params*.
    The result is injected into session context via ``inject_result``.

    Supports SWE-bench, pytest, and simple symbol entry formats.
    Automatically scopes ``analyze_package`` to the test directory
    for faster analysis on large repos.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params: Must include ``entry`` (symbol name to trace from).
                Optional ``max_depth`` (default 5), ``cross_module`` (default False).

        Returns:
            HookResult with ``trace`` list in metadata on success.
        """
        entry = params.get("entry")
        if not entry:
            return HookResult.fail("Missing required param 'entry'")

        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path)
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            # Lazy imports
            global analyze_package, trace_flow
            if analyze_package is None:
                from axm_ast.core.analyzer import (
                    analyze_package as _ap,
                )
                from axm_ast.core.flows import trace_flow as _tf

                analyze_package = _ap
                trace_flow = _tf

            # Parse entry format and scope analysis path
            symbol_name, test_dir = _parse_entry(entry)
            scoped_path = _resolve_scope(working_dir, test_dir)

            pkg = analyze_package(scoped_path)
            max_depth = int(params.get("max_depth", 5))
            cross_module = bool(params.get("cross_module", False))

            steps = trace_flow(
                pkg,
                symbol_name,
                max_depth=max_depth,
                cross_module=cross_module,
                detail="source",
            )
            return HookResult.ok(
                trace=[s.model_dump(exclude_none=True) for s in steps],
            )
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Trace failed: {exc}")
