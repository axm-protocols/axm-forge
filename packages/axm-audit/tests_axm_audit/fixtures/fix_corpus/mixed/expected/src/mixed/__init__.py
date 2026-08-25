"""mixed fixture package — combines all five fix stages in one mini-package."""

from __future__ import annotations

from mixed.alpha import alpha
from mixed.beta import beta
from mixed.gamma import gamma

__all__ = ["alpha", "beta", "gamma"]
