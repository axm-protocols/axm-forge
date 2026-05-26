"""Core module for axm-edit.

Contains the batch editing engine and git checkpoint logic.
"""

from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.core.engine import batch_apply

__all__ = ["batch_apply", "create_checkpoint", "rollback"]
