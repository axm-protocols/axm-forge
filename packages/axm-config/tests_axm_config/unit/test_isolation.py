from __future__ import annotations

from pathlib import Path

import axm_config

__all__: list[str] = []

_PATH_KEYS = (
    "tickets_db",
    "warden_socket",
    "warden_log",
    "sessions_root",
    "quality_dir",
    "protocols_dir",
)


def _contained_paths(root: Path) -> dict[str, Path]:
    return {key: root / key for key in _PATH_KEYS}


def test_is_isolated_reports_one_escaping_path() -> None:
    """AC1: nomme l'unique chemin qui s'échappe de la racine."""
    root = Path("/p/root")
    paths = _contained_paths(root)
    paths["tickets_db"] = Path("/elsewhere/tickets.db")

    result = axm_config.is_isolated(root, paths)

    assert result == (False, ["tickets_db"])


def test_is_isolated_sorts_all_escaping_path_keys() -> None:
    """AC1: nomme et trie toutes les clés dont les chemins s'échappent."""
    root = Path("/p/root")
    paths = _contained_paths(root)
    paths["tickets_db"] = Path("/elsewhere/tickets.db")
    paths["protocols_dir"] = Path("/outside/protocols")

    _isolated, escapes = axm_config.is_isolated(root, paths)

    assert escapes == ["protocols_dir", "tickets_db"]


def test_is_isolated_accepts_all_six_contained_paths() -> None:
    """AC2: accepte les six chemins lorsqu'ils sont sous la racine."""
    root = Path("/p/root")

    result = axm_config.is_isolated(root, _contained_paths(root))

    assert result == (True, [])
