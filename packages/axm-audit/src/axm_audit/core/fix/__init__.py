"""Deterministic test-suite auto-fixer.

See ``docs/fix_pipeline.md`` for pipeline architecture and bug-class
history. Public API: :func:`run`, :func:`format_report`,
:class:`PipelineReport`, :class:`FileOp`, :class:`OpKind`.
"""

from __future__ import annotations

from .models import FileOp, OpKind, PipelineReport
from .pipeline import run
from .report import format_report

__all__ = ["FileOp", "OpKind", "PipelineReport", "format_report", "run"]
