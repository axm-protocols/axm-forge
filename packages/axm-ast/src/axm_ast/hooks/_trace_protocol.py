"""Shared Protocol mirroring ``axm_ast.core.flows.trace_flow``.

Used by hooks that lazy-import ``trace_flow`` (to keep tree-sitter out of
hook discovery) yet still want static analysis to track the signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from axm_ast.core.flows import FlowStep
    from axm_ast.models.calls import CallSite
    from axm_ast.models.nodes import PackageInfo

__all__ = ["_TraceFlow"]


class _TraceFlow(Protocol):
    """Protocol mirroring ``axm_ast.core.flows.trace_flow``."""

    def __call__(  # noqa: PLR0913 — mirrors core.flows.trace_flow signature
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
