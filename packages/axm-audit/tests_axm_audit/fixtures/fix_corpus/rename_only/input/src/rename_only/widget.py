"""Widget module of rename_only fixture."""

from __future__ import annotations

__all__ = ["make_widget"]


def make_widget(label: str) -> dict[str, str]:
    """Return a widget descriptor."""
    return {"label": label}
