"""Practice rules — code quality patterns via AST.

One module per rule. Importing this package fires the
``@register_rule`` decorators of each submodule.
"""

from __future__ import annotations

from axm_audit.core.rules.practices.bare_except import BareExceptRule
from axm_audit.core.rules.practices.blocking_io import BlockingIORule
from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule
from axm_audit.core.rules.practices.mirror import MirrorRule

__all__ = [
    "BareExceptRule",
    "BlockingIORule",
    "DocstringCoverageRule",
    "MirrorRule",
]
