from __future__ import annotations

import re
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture import GodClassRule


def _make_god_class(name: str, *, lines: int = 600, methods: int = 25) -> str:
    """Generate a Python class that exceeds god-class thresholds."""
    parts = [f"class {name}:"]
    for i in range(methods):
        parts.append(f"    def method_{i}(self):")
        parts.append("        pass")
    while len(parts) < lines:
        parts.append(f"    # padding {len(parts)}")
    return "\n".join(parts) + "\n"


def _make_small_class(name: str) -> str:
    return f"class {name}:\n    def run(self):\n        pass\n"


def _setup_project(tmp_path: Path, files: dict[str, str]) -> Path:
    src = tmp_path / "src"
    for relpath, content in files.items():
        fpath = src / relpath
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content)
    return tmp_path


@pytest.fixture()
def rule() -> GodClassRule:
    return GodClassRule()


class TestGodClassTextFormat:
    """AC1: text uses format bullet basename:Class NL/MM."""

    def test_god_class_text_format(self, rule: GodClassRule, tmp_path: Path) -> None:
        project = _setup_project(
            tmp_path,
            {
                "mypkg/engine.py": _make_god_class("AuditEngine"),
            },
        )
        result = rule.check(project)

        assert result.text is not None
        assert not result.passed
        lines = result.text.strip().split("\n")
        assert len(lines) == 1
        # Must match: \u2022 engine.py:AuditEngine {N}L/{M}M
        pattern = r"^\u2022 engine\.py:AuditEngine \d+L/\d+M$"
        assert re.match(pattern, lines[0]), (
            f"Line did not match expected format: {lines[0]!r}"
        )
        # No leading spaces
        assert not lines[0].startswith(" ")

    def test_god_class_text_none_when_passed(
        self, rule: GodClassRule, tmp_path: Path
    ) -> None:
        """AC2: text=None when passed=True."""
        project = _setup_project(
            tmp_path,
            {
                "mypkg/small.py": _make_small_class("TinyHelper"),
            },
        )
        result = rule.check(project)

        assert result.passed
        assert result.text is None


class TestGodClassEdgeCases:
    def test_filename_collision_different_dirs(
        self, rule: GodClassRule, tmp_path: Path
    ) -> None:
        """Two god classes in different dirs, same filename — class disambiguates."""
        project = _setup_project(
            tmp_path,
            {
                "mypkg/core/heavy.py": _make_god_class("CoreProcessor"),
                "mypkg/utils/heavy.py": _make_god_class("UtilProcessor"),
            },
        )
        result = rule.check(project)

        assert result.text is not None
        lines = result.text.strip().split("\n")
        assert len(lines) == 2
        # Both show heavy.py but different class names
        texts = sorted(lines)
        assert re.match(r"^\u2022 heavy\.py:CoreProcessor \d+L/\d+M$", texts[0])
        assert re.match(r"^\u2022 heavy\.py:UtilProcessor \d+L/\d+M$", texts[1])

    def test_deeply_nested_file(self, rule: GodClassRule, tmp_path: Path) -> None:
        """Deeply nested file shows only basename in text, full path in details."""
        nested = "axm_audit/core/rules/contrib/experimental/heavy.py"
        project = _setup_project(
            tmp_path,
            {
                nested: _make_god_class("HeavyClass"),
            },
        )
        result = rule.check(project)

        assert result.text is not None
        lines = result.text.strip().split("\n")
        assert len(lines) == 1
        # Text shows only basename
        assert re.match(r"^\u2022 heavy\.py:HeavyClass \d+L/\d+M$", lines[0])
        # Details retains full relative path
        assert result.details is not None
        god = result.details["god_classes"][0]
        assert "contrib/experimental/heavy.py" in god["file"]


class TestGodClassDetailsUnchanged:
    """AC3: details dict remains unchanged."""

    def test_details_structure(self, rule: GodClassRule, tmp_path: Path) -> None:
        project = _setup_project(
            tmp_path,
            {
                "mypkg/big.py": _make_god_class("BigClass"),
            },
        )
        result = rule.check(project)

        assert result.details is not None
        assert "god_classes" in result.details
        assert "score" in result.details
        god = result.details["god_classes"][0]
        assert set(god.keys()) >= {"name", "file", "lines", "methods"}
        assert god["name"] == "BigClass"
