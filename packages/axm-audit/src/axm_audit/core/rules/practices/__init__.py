"""Practice rules — code quality patterns via AST.

One module per rule. Importing this package fires the
``@register_rule`` decorators of each submodule.
"""

from __future__ import annotations

from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule
from axm_audit.core.rules.practices.bare_except import BareExceptRule
from axm_audit.core.rules.practices.blocking_io import BlockingIORule
from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule
from axm_audit.core.rules.practices.env_credentials import EnvCredentialsRule
from axm_audit.core.rules.practices.mirror import MirrorRule
from axm_audit.core.rules.practices.tool_secret_locations import (
    ToolSecretLocationRule,
)

__all__ = [
    "AntiMirrorRule",
    "BareExceptRule",
    "BlockingIORule",
    "DocstringCoverageRule",
    "EnvCredentialsRule",
    "MirrorRule",
    "ToolSecretLocationRule",
]
