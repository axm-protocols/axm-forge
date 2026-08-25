"""axm-edit — Atomic batch file editing for AI agents.

Replace, create, and delete files in a single atomic operation.
"""

from axm_edit._version import __version__
from axm_edit.core.checkpoint import rollback
from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    Operation,
    ReplaceOp,
    RollbackResult,
    ValidationError,
)

__all__ = [
    "BatchResult",
    "CreateOp",
    "DeleteOp",
    "Edit",
    "Operation",
    "ReplaceOp",
    "RollbackResult",
    "ValidationError",
    "__version__",
    "batch_apply",
    "rollback",
]
