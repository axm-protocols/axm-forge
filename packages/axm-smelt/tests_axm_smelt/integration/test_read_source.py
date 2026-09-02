from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.mark.integration
def test_read_source_returns_exact_utf8_file_content(tmp_path: Path) -> None:
    """AC1: le contenu UTF-8 réel est rendu à l'identique, accents compris."""
    input_source = importlib.import_module("axm_smelt.core.input_source")
    source_path = tmp_path / "probe.txt"
    expected = "déjà écouté"
    source_path.write_text(expected, encoding="utf-8")

    result = input_source.read_source(input_path=str(source_path))

    assert result == expected


@pytest.mark.integration
def test_read_source_missing_file_names_exact_path(tmp_path: Path) -> None:
    """AC2: l'erreur d'un fichier absent contient son chemin exact."""
    input_source = importlib.import_module("axm_smelt.core.input_source")
    source_path = tmp_path / "absent.txt"

    with pytest.raises(input_source.InputSourceError) as exc_info:
        input_source.read_source(input_path=str(source_path))

    assert str(source_path) in str(exc_info.value)


@pytest.mark.integration
def test_read_source_invalid_utf8_names_exact_path(tmp_path: Path) -> None:
    """AC3: l'erreur de décodage UTF-8 contient le chemin exact."""
    input_source = importlib.import_module("axm_smelt.core.input_source")
    source_path = tmp_path / "latin.bin"
    source_path.write_bytes(b"\xff\xfe caf\xe9")

    with pytest.raises(input_source.InputSourceError) as exc_info:
        input_source.read_source(input_path=str(source_path))

    assert str(source_path) in str(exc_info.value)
