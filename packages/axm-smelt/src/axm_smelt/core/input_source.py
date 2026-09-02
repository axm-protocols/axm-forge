"""Résolution d'une source : chemin explicite, puis flux standard non interactif."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

__all__ = ["InputSourceError", "read_source", "resolve_text_source"]


class InputSourceError(ValueError):
    """Erreur de lecture ou de décodage d'une source d'entrée."""


def read_source(
    input_path: str | None = None,
    *,
    stdin: TextIO | None = None,
) -> str | None:
    """Lire le chemin explicite, sinon stdin s'il est non interactif."""
    if input_path is not None:
        try:
            return Path(input_path).read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError) as exc:
            raise InputSourceError(
                f"Impossible de lire la source {input_path}: {exc}"
            ) from exc

    if stdin is None or stdin.isatty():
        return None
    return stdin.read()


def resolve_text_source(
    data: str,
    input_path: str | None = None,
    *,
    stdin: TextIO | None = None,
) -> str:
    """Résoudre une donnée textuelle explicite, un chemin, puis stdin."""
    if data:
        return data
    if input_path is not None:
        return read_source(input_path, stdin=stdin) or ""
    try:
        return read_source(stdin=stdin) or ""
    except OSError:
        return ""
