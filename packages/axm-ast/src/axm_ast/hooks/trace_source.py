"""TraceSourceHook — enriched BFS trace with function source code.

Protocol hook that calls ``trace_flow(detail="source")`` and returns
the complete trace as ``HookResult`` metadata.  Registered as
``ast:trace-source`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from axm.hooks.base import HookResult

if TYPE_CHECKING:
    from axm_ast.core.flows import FlowStep
    from axm_ast.models.calls import CallSite
    from axm_ast.models.nodes import PackageInfo

logger = logging.getLogger(__name__)

__all__ = ["TraceSourceHook", "_parse_entry", "_resolve_scope"]


class _TraceFlow(Protocol):
    """Protocol mirroring ``axm_ast.core.flows.trace_flow``."""

    def __call__(  # noqa: PLR0913 — mirrors upstream trace_flow signature
        self,
        pkg: PackageInfo,
        entry: str,
        *,
        max_depth: int = ...,
        cross_module: bool = ...,
        detail: str = ...,
        callee_index: dict[tuple[str, str], list[CallSite]] | None = ...,
        exclude_stdlib: bool = ...,
    ) -> tuple[list[FlowStep], bool]: ...


# Lazy imports — avoid importing heavy tree-sitter at module level.
# Typed as Callable / Protocol so static analysis tracks signatures;
# ``None`` sentinel triggers the one-time load in ``execute``.
analyze_package: Callable[[Path], PackageInfo] | None = None
trace_flow: _TraceFlow | None = None

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

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``working_dir``).
            **params: Must include ``entry`` (symbol name to trace from).
                Optional ``max_depth`` (default 5), ``cross_module`` (default False).

        Returns:
            HookResult with ``trace`` list in metadata on success.
        """
        raw_entry = params.get("entry")
        if not raw_entry:
            return HookResult.fail("Missing required param 'entry'")
        if not isinstance(raw_entry, str):
            return HookResult.fail(f"entry must be str, got {type(raw_entry).__name__}")

        raw_path = params.get("path") or context.get("working_dir", ".")
        if not isinstance(raw_path, (str, Path)):
            return HookResult.fail(
                f"path must be str or Path, got {type(raw_path).__name__}"
            )
        working_dir = Path(raw_path)
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

            assert analyze_package is not None
            assert trace_flow is not None

            # Parse entry format and scope analysis path
            symbol_name, test_dir = _parse_entry(raw_entry)
            scoped_path = _resolve_scope(working_dir, test_dir)

            pkg = analyze_package(scoped_path)
            raw_max_depth = params.get("max_depth", 5)
            max_depth = (
                int(raw_max_depth) if isinstance(raw_max_depth, (int, str)) else 5
            )
            cross_module = bool(params.get("cross_module", False))

            steps, _truncated = trace_flow(
                pkg,
                symbol_name,
                max_depth=max_depth,
                cross_module=cross_module,
                detail="source",
            )
            return HookResult.ok(
                trace=[
                    cast("dict[str, object]", s.model_dump(exclude_none=True))
                    for s in steps
                ],
            )
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Trace failed: {exc}")
