"""Split from ``test_practices.py``."""

from pathlib import Path

import pytest


def _mk_src_module(tmp_path: Path, rel: str) -> None:
    p = tmp_path / "src" / "pkg" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if not (tmp_path / "src" / "pkg" / "__init__.py").exists():
        (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    p.write_text("x = 1\n")


def _mk_test(tmp_path: Path, rel: str) -> None:
    p = tmp_path / "tests" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("def test_x(): pass\n")


class TestAntiMirrorRuleIntegration:
    """Tests for AntiMirrorRule.

    Flags integration/e2e tests named after source modules.
    """

    @pytest.mark.parametrize(
        "test_dir",
        [
            pytest.param("integration", id="integration"),
            pytest.param("e2e", id="e2e"),
        ],
    )
    def test_anti_mirror_flags_test_named_after_source(
        self, tmp_path: Path, test_dir: str
    ) -> None:
        """AC1-AC3: integration/e2e test named after a source module is flagged."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_test(tmp_path, f"{test_dir}/test_foo.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert f"tests/{test_dir}/test_foo.py" in result.details["anti_mirror"]

    def test_anti_mirror_passes_when_scenario_named(self, tmp_path: Path) -> None:
        """AC4: scenario-named tests pass.

        No source-name collisions pass with score 100.
        """
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_src_module(tmp_path, "bar.py")
        _mk_test(tmp_path, "integration/test_cache_invalidation_on_write.py")
        _mk_test(tmp_path, "e2e/test_submit_order.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.score == 100
        assert result.details is not None
        assert result.details["anti_mirror"] == []

    def test_score_decreases_per_violation(self, tmp_path: Path) -> None:
        """AC5: each violation deducts 15 points from 100."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_test(tmp_path, "integration/test_foo.py")

        result1 = AntiMirrorRule().check(tmp_path)
        assert result1.score == 85

        _mk_src_module(tmp_path, "bar.py")
        _mk_test(tmp_path, "integration/test_bar.py")

        result2 = AntiMirrorRule().check(tmp_path)
        assert result2.score == 70

    def test_score_clamped_at_zero(self, tmp_path: Path) -> None:
        """AC5: score is clamped at 0; 10 violations cannot go negative."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        for i in range(10):
            name = f"mod{i}.py"
            _mk_src_module(tmp_path, name)
            _mk_test(tmp_path, f"integration/test_mod{i}.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.score == 0
        assert result.passed is False

    def test_details_anti_mirror_lists_relative_paths(self, tmp_path: Path) -> None:
        """AC6: details[anti_mirror] entries are tests/-relative.

        Not absolute or basenames.
        """
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_src_module(tmp_path, "bar.py")
        _mk_test(tmp_path, "integration/test_foo.py")
        _mk_test(tmp_path, "e2e/test_bar.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.details is not None
        entries = result.details["anti_mirror"]
        assert len(entries) == 2
        for entry in entries:
            assert entry.startswith("tests/"), entry
            assert not entry.startswith("/"), entry
            assert "/" in entry, entry

    def test_fix_hint_suggests_scenario_rename(self, tmp_path: Path) -> None:
        """AC7: fix_hint suggests scenario-style rename."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "data.py")
        _mk_test(tmp_path, "integration/test_data.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.fix_hint is not None
        assert "rename" in result.fix_hint.lower()
        assert (
            "scenario" in result.fix_hint.lower()
            or "describe" in result.fix_hint.lower()
        )

    def test_text_field_compact_single_bullet_line(self, tmp_path: Path) -> None:
        """AC8: text is one line starting with '• anti-mirror:' listing the files."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        for name in ("a", "b", "c"):
            _mk_src_module(tmp_path, f"{name}.py")
            _mk_test(tmp_path, f"integration/test_{name}.py")

        result = AntiMirrorRule().check(tmp_path)

        text = (result.text or "").rstrip("\n")
        assert "\n" not in text
        assert text.startswith("• anti-mirror:")
        for name in ("a", "b", "c"):
            assert f"test_{name}.py" in text

    def test_text_field_truncates_with_plus_more(self, tmp_path: Path) -> None:
        """AC8: text shows first 5 entries, then a (+N more) suffix."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        for i in range(8):
            _mk_src_module(tmp_path, f"mod{i}.py")
            _mk_test(tmp_path, f"integration/test_mod{i}.py")

        result = AntiMirrorRule().check(tmp_path)

        text = result.text or ""
        assert "(+3 more)" in text

    def test_exempt_path_excludes_anti_mirror(self, tmp_path: Path) -> None:
        """AC9: exempt_paths-matched sources skip anti-mirror."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "commands/data.py")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.axm-audit.mirror]\nexempt_paths = ["commands/*.py"]\n'
        )
        _mk_test(tmp_path, "integration/test_data.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["anti_mirror"] == []

    def test_conftest_and_init_not_flagged(self, tmp_path: Path) -> None:
        """AC10: conftest.py and __init__.py are never flagged (no test_ prefix)."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        (tmp_path / "tests" / "integration").mkdir(parents=True)
        (tmp_path / "tests" / "integration" / "conftest.py").write_text("")
        (tmp_path / "tests" / "integration" / "__init__.py").write_text("")
        (tmp_path / "tests" / "e2e").mkdir(parents=True)
        (tmp_path / "tests" / "e2e" / "conftest.py").write_text("")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["anti_mirror"] == []

    def test_unit_tests_not_walked(self, tmp_path: Path) -> None:
        """AC13: tests/unit/ is never walked — unit-mirror is MirrorRule's job."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_test(tmp_path, "unit/test_foo.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["anti_mirror"] == []

    def test_no_integration_or_e2e_dir_passes(self, tmp_path: Path) -> None:
        """AC11: no integration or e2e dir means pass.

        Score 100 when both are absent.
        """
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        (tmp_path / "tests" / "unit").mkdir(parents=True)

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.score == 100

    def test_only_integration_dir_present(self, tmp_path: Path) -> None:
        """AC11: only tests/integration present (no e2e) and no violations → pass."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        _mk_src_module(tmp_path, "foo.py")
        _mk_test(tmp_path, "integration/test_some_scenario.py")

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True

    def test_rule_id_value(self, tmp_path: Path) -> None:
        """AC1: rule_id is PRACTICE_TEST_SCENARIO_NAMING."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        result = AntiMirrorRule().check(tmp_path)

        assert result.rule_id == "PRACTICE_TEST_SCENARIO_NAMING"

    def test_anti_mirror_suppressed_on_k1_canonical_axm_bib_topology(
        self, tmp_path: Path
    ) -> None:
        """AC1, AC6: reproduces axm-bib test_extract.py topology — suppressed."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        pkg_dir = tmp_path / "src" / "axm_bib"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "extract.py").write_text("def extract():\n    return 1\n")
        (pkg_dir / "cli.py").write_text("def extract():\n    return 2\n")
        test_dir = tmp_path / "tests" / "integration"
        test_dir.mkdir(parents=True)
        (test_dir / "test_extract.py").write_text(
            "from axm_bib.cli import extract\n\n"
            "def test_extract():\n    assert extract() == 2\n"
        )

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["anti_mirror"] == []

    def test_anti_mirror_still_fires_on_split_topology(self, tmp_path: Path) -> None:
        """AC2: K>=2 distinct tuples on a mirrored stem — violation present."""
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        pkg_dir = tmp_path / "src" / "pkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "foo.py").write_text(
            "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
        )
        test_dir = tmp_path / "tests" / "integration"
        test_dir.mkdir(parents=True)
        (test_dir / "test_foo.py").write_text(
            "from pkg.foo import foo, bar\n\n"
            "def test_foo():\n    assert foo() == 1\n\n"
            "def test_bar():\n    assert bar() == 2\n"
        )

        result = AntiMirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert "tests/integration/test_foo.py" in result.details["anti_mirror"]
