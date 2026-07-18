"""Documentation-gate schema surface.

Re-exports the public documentation-gate finding types.
"""

from __future__ import annotations

from .findings import DocGateFinding, FindingKind

__all__ = ["DocGateFinding", "FindingKind"]
