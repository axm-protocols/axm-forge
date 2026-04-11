"""axm-smelt - Deterministic token compaction for LLM inputs."""

from __future__ import annotations

from axm_smelt.core.counter import count
from axm_smelt.core.models import Format, SmeltReport
from axm_smelt.core.pipeline import check, smelt

try:
    from axm_smelt._version import __version__
except Exception:  # noqa: BLE001
    __version__ = "0.0.0"

__all__ = ["Format", "SmeltReport", "__version__", "check", "count", "smelt"]
