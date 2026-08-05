"""CouplingGapsTool — surface lower-bound coupling gaps for a symbol.

Thin AXMTool wrapper over the already-shipping
``axm_ast.core.coupling_gaps.analyze_coupling_gaps`` analysis engine. Reads a
package, delegates the three coupling passes (reference, structural Protocol/ABC
and contract-literal), and renders a dual-format ``ToolResult`` — the raw
per-symbol collections under ``data`` and a compact caveat + counts under
``text``. It never writes to the analysed package.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_ast.tools._base import safe_execute

logger = logging.getLogger(__name__)

__all__ = ["CouplingGapsTool"]

_CAVEAT = (
    "Lower-bound estimate: surfaces reference, structural Protocol/ABC and "
    "contract-literal coupling only. Matching is shape/literal based (no type "
    "inference), so dynamically-resolved sites may be missed — treat the counts "
    "as a floor, not a total."
)


def _count_sites(groups: object) -> int:
    """Sum the site counts across a per-symbol coupling collection.

    Accepts the raw ``dict[str, list[...]]`` shape (or anything mapping-like
    whose values are sequences); non-conforming inputs contribute zero so the
    renderer stays total on partial/fabricated results.
    """
    if not isinstance(groups, Mapping):
        return 0
    return sum(len(v) for v in groups.values() if isinstance(v, Sequence))


def _render_text(result: Mapping[str, object]) -> str:
    """Render the coupling-gaps result as compact text.

    Emits the lower-bound caveat plus the reference/protocol/value site counts
    so a reader sees, at a glance, how much coupling the reference-only walk
    (``ast_impact``) misses.
    """
    reference_count = _count_sites(result.get("reference_coupled"))
    protocol_count = _count_sites(result.get("protocol_coupled"))
    value_count = _count_sites(result.get("value_coupled"))
    lines = [
        "ast_coupling_gaps | lower-bound coupling report",
        _CAVEAT,
        f"reference-coupled sites: {reference_count}",
        f"protocol-coupled sites: {protocol_count}",
        f"value-coupled sites: {value_count}",
    ]
    return "\n".join(lines)


class CouplingGapsTool(AXMTool):
    """Surface the coupling a reference-only walk misses for a symbol.

    Registered as ``ast_coupling_gaps`` via the axm.tools entry point.
    Read-only: it loads the package and delegates to
    :func:`axm_ast.core.coupling_gaps.analyze_coupling_gaps`, never writing to
    the analysed tree.
    """

    agent_hint: str = (
        "Surface lower-bound coupling gaps for a symbol — the structural"
        " Protocol/ABC and contract-literal sites ast_impact's reference walk"
        " misses. Read-only; omit the symbol to scan the whole public API."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_coupling_gaps"

    @safe_execute
    def execute(
        self,
        *,
        path: str = ".",
        symbol: str | None = None,
        symbols: list[str] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Report the lower-bound coupling gaps for one or more symbols.

        Args:
            path: Path to the package directory to analyse.
            symbol: A single symbol to analyse.
            symbols: A batch of symbols to analyse. When both ``symbol`` and
                ``symbols`` are omitted, the package's public API is scanned.
            **kwargs: Ignored extra options (interface tolerance).

        Returns:
            ToolResult whose ``data`` carries the ``reference_coupled``,
            ``protocol_coupled`` and ``value_coupled`` per-symbol collections,
            and whose ``text`` renders the lower-bound caveat plus site counts.
        """
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {project_path}")

        from axm_ast.core.cache import get_package
        from axm_ast.core.coupling_gaps import analyze_coupling_gaps

        pkg = get_package(project_path)
        targets = self._resolve_targets(pkg, symbol, symbols)
        if not targets:
            return ToolResult(success=False, error="no symbols available to analyse")

        result = analyze_coupling_gaps(pkg, targets)
        return ToolResult(
            success=True,
            data=cast("dict[str, object]", dict(result)),
            text=_render_text(result),
        )

    @staticmethod
    def _resolve_targets(
        pkg: object,
        symbol: str | None,
        symbols: list[str] | None,
    ) -> list[str]:
        """Resolve the symbols to analyse.

        Explicit ``symbols``/``symbol`` win; otherwise fall back to the
        package's public API so a bare ``ast_coupling_gaps <pkg>`` invocation
        yields a whole-package report.
        """
        if symbols:
            return list(symbols)
        if symbol:
            return [symbol]
        public_api = getattr(pkg, "public_api", [])
        names = [getattr(member, "name", None) for member in public_api]
        return list(dict.fromkeys(n for n in names if isinstance(n, str)))
