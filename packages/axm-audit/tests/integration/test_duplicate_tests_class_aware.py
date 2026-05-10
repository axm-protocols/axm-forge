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


IDENTICAL_BODY = (
    "    def test_run(self):\n        result = process(1)\n        assert result == 2\n"
)


def test_cross_class_pair_demoted(tmp_path: Path) -> None:
    file_a = "class TestFoo:\n" + IDENTICAL_BODY
    file_b = "class TestBar:\n" + IDENTICAL_BODY
    project = _write(tmp_path, {"test_a.py": file_a, "test_b.py": file_b})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_run"})
    assert pair is not None
    assert pair["signal"] == "ambiguous_distinct_class"


@pytest.mark.parametrize(
    ("files", "pair_names"),
    [
        pytest.param(
            {
                "test_a.py": (
                    "class TestFoo:\n"
                    "    def test_first(self):\n"
                    "        result = process(1)\n"
                    "        assert result == 2\n"
                    "    def test_second(self):\n"
                    "        result = process(1)\n"
                    "        assert result == 2\n"
                ),
            },
            {"test_first", "test_second"},
            id="same_class_pair_still_clustered",
        ),
        pytest.param(
            {
                "test_a.py": (
                    "def test_alpha():\n"
                    "    result = process(1)\n"
                    "    assert result == 2\n"
                ),
                "test_b.py": (
                    "def test_beta():\n"
                    "    result = process(1)\n"
                    "    assert result == 2\n"
                ),
            },
            {"test_alpha", "test_beta"},
            id="module_level_pair_unaffected",
        ),
    ],
)
def test_pair_clusters_with_signal1_or_signal3(
    tmp_path: Path, files: dict[str, str], pair_names: set[str]
) -> None:
    project = _write(tmp_path, files)

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], pair_names)
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))
