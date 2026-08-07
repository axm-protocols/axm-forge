"""Unit mirror of :mod:`axm_edit.services.line_length` (pure parsing).

No filesystem access: the TOML text is supplied in memory.
"""

from __future__ import annotations

from axm_edit.services.line_length import parse_line_length


def test_declared_line_length_is_extracted_from_toml_text() -> None:
    """AC4: the ruff ``line-length`` declared in the TOML is returned."""
    toml_text = "[tool.ruff]\nline-length = 100\n"

    assert parse_line_length(toml_text) == 100


def test_missing_line_length_key_yields_none() -> None:
    """AC4: a TOML without ``line-length`` resolves to ``None``."""
    toml_text = "[tool.ruff]\ntarget-version = 'py312'\n"

    assert parse_line_length(toml_text) is None
