"""Validate revision provenance at the filesystem boundary."""

from pathlib import Path

import pytest

from axm_ingot import QualityOrigin

pytestmark = pytest.mark.integration


def test_origin_round_trip_and_invalid_payloads(tmp_path: Path) -> None:
    source = tmp_path.resolve() / "source" / "demo"
    origin = QualityOrigin.from_data(
        {"path": str(source), "sha": "a" * 40, "branch": "dev"}
    )
    assert origin == QualityOrigin(source, "a" * 40, "dev")
    assert QualityOrigin.from_data(None) is None
    for payload in (
        {"path": str(source), "sha": "short", "branch": "dev"},
        {"path": "relative", "sha": "a" * 40, "branch": "dev"},
        {"path": str(source), "sha": "a" * 40, "branch": ""},
        {"path": str(source), "sha": "a" * 40, "branch": "dev\n"},
        {"path": str(source), "sha": "a" * 40},
    ):
        with pytest.raises(ValueError):
            QualityOrigin.from_data(payload)


def test_origin_refuses_symlink_alias(tmp_path: Path) -> None:
    source = tmp_path.resolve() / "source"
    source.mkdir()
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="canonical"):
        QualityOrigin.from_data({"path": str(alias), "sha": "b" * 40, "branch": "dev"})
