from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule


def _write(tmp_path: Path, files: dict[str, str]) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, body in files.items():
        (tests / name).write_text(body)
    return tmp_path


def _find_pair(
    clusters: list[dict[str, Any]], names: set[str]
) -> dict[str, Any] | None:
    for c in clusters:
        cluster_names = {t["name"] for t in c["tests"]}
        if names.issubset(cluster_names):
            return c
    return None


def test_one_with_raises_one_without_demoted(tmp_path: Path) -> None:
    body = (
        "import pytest\n\n"
        "def test_with_raises():\n"
        "    with pytest.raises(ValueError):\n"
        "        fn(1)\n\n"
        "def test_without_raises():\n"
        "    result = fn(1)\n"
        "    assert result == 0\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(
        result.metadata["clusters"], {"test_with_raises", "test_without_raises"}
    )
    assert pair is not None
    assert pair["signal"] == "ambiguous_raises_divergence"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            (
                "import pytest\n\n"
                "def test_first():\n"
                "    with pytest.raises(ValueError):\n"
                "        fn(1)\n\n"
                "def test_second():\n"
                "    with pytest.raises(ValueError):\n"
                "        fn(1)\n"
            ),
            id="both_with_raises_still_clustered",
        ),
        pytest.param(
            (
                "def test_first():\n"
                "    result = fn(1)\n"
                "    assert result == 0\n\n"
                "def test_second():\n"
                "    result = fn(1)\n"
                "    assert result == 0\n"
            ),
            id="neither_with_raises_unaffected",
        ),
    ],
)
def test_raises_symmetric_pair_clusters(tmp_path: Path, body: str) -> None:
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))
