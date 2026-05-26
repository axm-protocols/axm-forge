"""Private CST primitives shared by move/rename/split tooling.

This sub-package is intentionally internal: symbols here are subject to
change without notice. External consumers should use the public
``axm_anvil`` API instead.
"""

from __future__ import annotations

from axm_anvil._cst.blocks import Block, _extract_blocks
from axm_anvil._cst.overloads import _detect_overload_group
from axm_anvil._cst.transformers import _RemoveSymbols
from axm_anvil._cst.visitors import _dotted_name, _ReferenceCollector

__all__ = [
    "Block",
    "_ReferenceCollector",
    "_RemoveSymbols",
    "_detect_overload_group",
    "_dotted_name",
    "_extract_blocks",
]
