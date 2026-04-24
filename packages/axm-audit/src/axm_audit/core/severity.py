"""Re-export of the :class:`Severity` enum.

Thin shim exposing :class:`axm_audit.models.results.Severity` at a shorter
import path for rules that only need the enum.
"""

from __future__ import annotations

from axm_audit.models.results import Severity

__all__ = ["Severity"]
