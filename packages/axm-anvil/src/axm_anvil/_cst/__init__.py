"""Private CST primitives shared by move/rename/split tooling.

This sub-package is intentionally internal: symbols here are subject to
change without notice. External consumers should use the public
``axm_anvil`` API instead.
"""

from __future__ import annotations

from axm_anvil._cst.blocks import Block, extract_blocks
from axm_anvil._cst.overloads import detect_overload_group
from axm_anvil._cst.transformers import RemoveSymbols
from axm_anvil._cst.visitors import ReferenceCollector, dotted_name

__all__ = [
    "Block",
    "ReferenceCollector",
    "RemoveSymbols",
    "detect_overload_group",
    "dotted_name",
    "extract_blocks",
]
