"""Deterministic test-suite auto-fixer (split layout, 12 modules).

Re-exports the public API of the legacy ``tuple_fix_proto.py`` so that
imports remain stable across the split.
"""
from __future__ import annotations

from .models import FileOp, OpKind, PipelineReport
from .pipeline import run
from .report import format_report

__all__ = ["FileOp", "OpKind", "PipelineReport", "format_report", "run"]
