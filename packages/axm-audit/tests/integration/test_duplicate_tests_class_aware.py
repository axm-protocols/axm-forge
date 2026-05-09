from __future__ import annotations

from pathlib import Path
from typing import Any

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


def test_same_class_pair_still_clustered(tmp_path: Path) -> None:
    body = (
        "class TestFoo:\n"
        "    def test_first(self):\n"
        "        result = process(1)\n"
        "        assert result == 2\n"
        "    def test_second(self):\n"
        "        result = process(1)\n"
        "        assert result == 2\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


def test_module_level_pair_unaffected(tmp_path: Path) -> None:
    body_a = "def test_alpha():\n    result = process(1)\n    assert result == 2\n"
    body_b = "def test_beta():\n    result = process(1)\n    assert result == 2\n"
    project = _write(tmp_path, {"test_a.py": body_a, "test_b.py": body_b})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_alpha", "test_beta"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))
