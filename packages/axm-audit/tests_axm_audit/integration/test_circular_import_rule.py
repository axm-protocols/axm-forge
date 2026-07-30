"""Split from ``test_architecture.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.architecture import GodClassRule


@pytest.fixture()
def rule() -> GodClassRule:
    return GodClassRule()


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
