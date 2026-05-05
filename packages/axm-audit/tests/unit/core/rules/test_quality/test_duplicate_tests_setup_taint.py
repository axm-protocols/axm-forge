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


def _has_pair(clusters: list[dict[str, Any]], names: set[str]) -> bool:
    for c in clusters:
        cluster_names = {t["name"] for t in c["tests"]}
        if names.issubset(cluster_names):
            return True
    return False


def _find_pair(
    clusters: list[dict[str, Any]], names: set[str]
) -> dict[str, Any] | None:
    for c in clusters:
        cluster_names = {t["name"] for t in c["tests"]}
        if names.issubset(cluster_names):
            return c
    return None


def test_distinct_self_attr_sut_not_clustered(tmp_path: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setUp(self):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})


def test_same_self_attr_sut_still_clustered(tmp_path: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setUp(self):\n"
        "        self.parser = Parser()\n"
        "    def test_first(self):\n"
        "        result = self.parser.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser.run()\n"
        "        assert result == 1\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


def test_setup_method_variant(tmp_path: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setup_method(self, method):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})


def test_pytest_fixture_class_attr(tmp_path: Path) -> None:
    body = (
        "import pytest\n\n"
        "class TestX:\n"
        "    @pytest.fixture(autouse=True)\n"
        "    def _setup(self):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})
