"""Integration tests for Architecture Rules (filesystem I/O via tmp_path)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture import GodClassRule


class TestCircularImportRuleIO:
    """Tests for CircularImportRule that touch the filesystem."""

    def test_no_cycles_passes(self, tmp_path: Path) -> None:
        """Clean project with no circular imports passes."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("from src import b\n")
        (src / "b.py").write_text("x = 1\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["cycles"] == []

    def test_detects_simple_cycle(self, tmp_path: Path) -> None:
        """Detects A→B→A cycle."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # Use direct imports that match module names
        (src / "a.py").write_text("import b\n")
        (src / "b.py").write_text("import a\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["cycles"]) > 0

    def test_text_strips_package_prefix(self, tmp_path: Path) -> None:
        """Text output strips the common package prefix from module names."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        pkg = src / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("import mypkg.b\n")
        (pkg / "b.py").write_text("import mypkg.a\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.text is not None
        # Should show relative paths, not FQN
        assert "mypkg." not in result.text
        assert "\u2192" in result.text

    def test_text_no_prefix_strip_for_bare_modules(self, tmp_path: Path) -> None:
        """Modules without dots keep their names unchanged."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("import b\n")
        (src / "b.py").write_text("import a\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.text is not None
        # Bare names (no dot) should remain as-is
        assert "a" in result.text
        assert "b" in result.text


class TestGodClassRuleIO:
    """Tests for GodClassRule that touch the filesystem."""

    def test_small_class_passes(self, tmp_path: Path) -> None:
        """Class under thresholds passes."""
        from axm_audit.core.rules.architecture import GodClassRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "small.py").write_text('''
class SmallClass:
    """A small class."""

    def method_a(self) -> None:
        pass

    def method_b(self) -> None:
        pass
''')

        rule = GodClassRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_detects_class_with_many_methods(self, tmp_path: Path) -> None:
        """Flags class with >15 methods."""
        from axm_audit.core.rules.architecture import GodClassRule

        src = tmp_path / "src"
        src.mkdir()
        methods = "\n".join(
            f"    def method_{i}(self) -> None:\n        pass\n" for i in range(20)
        )
        (src / "god.py").write_text(f"class GodClass:\n{methods}")

        rule = GodClassRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["god_classes"]) > 0


class TestCouplingMetricRuleIO:
    """Tests for CouplingMetricRule that touch the filesystem."""

    def test_low_coupling_passes(self, tmp_path: Path) -> None:
        """Low coupling project passes."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("x = 1\n")
        (src / "b.py").write_text("y = 2\n")

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_detects_high_coupling(self, tmp_path: Path) -> None:
        """Flags module with many imports (high fan-out)."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # Create many distinct modules
        for i in range(15):
            (src / f"mod_{i}.py").write_text(f"val_{i} = {i}\n")
        # Create hub module that imports all (distinct module names)
        imports = "\n".join(f"import mod_{i}" for i in range(15))
        (src / "hub.py").write_text(imports)

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["max_fan_out"] >= 10
        assert result.details["n_over_threshold"] >= 1


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
        assert result.score is not None
        god = result.details["god_classes"][0]
        assert set(god.keys()) >= {"name", "file", "lines", "methods"}
        assert god["name"] == "BigClass"
