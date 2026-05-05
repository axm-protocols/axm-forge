"""Integration tests for Architecture Rules (filesystem I/O via tmp_path)."""

from __future__ import annotations

from pathlib import Path


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
