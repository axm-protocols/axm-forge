"""Tests for load_exclusions — per-package check exclusion config."""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks._utils import load_exclusions

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestLoadExclusionsEmpty:
    def test_no_axm_init_section(self, tmp_path: Path) -> None:
        """pyproject.toml with no [tool.axm-init] → empty set."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        assert load_exclusions(tmp_path) == set()


class TestLoadExclusionsValid:
    def test_valid_exclusions(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = ["cli", "changelog"]
        """)
        )
        assert load_exclusions(tmp_path) == {"cli", "changelog"}


class TestLoadExclusionsMissingKey:
    def test_section_but_no_exclude(self, tmp_path: Path) -> None:
        """[tool.axm-init] exists but no exclude key."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            other_key = true
        """)
        )
        assert load_exclusions(tmp_path) == set()


class TestLoadExclusionsNoToml:
    def test_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml at path → empty set."""
        assert load_exclusions(tmp_path) == set()


class TestLoadExclusionsInvalidWarns:
    def test_non_string_entries_warn(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-string entries in exclude list → logged warning."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = [42]
        """)
        )
        with caplog.at_level(logging.WARNING):
            result = load_exclusions(tmp_path)
        assert result == set()
        assert "Invalid exclusion entry" in caplog.text

    def test_non_list_value_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """exclude = 42 (not list, not string) → logged warning."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = 42
        """)
        )
        with caplog.at_level(logging.WARNING):
            result = load_exclusions(tmp_path)
        assert result == set()
        assert "Invalid [tool.axm-init].exclude" in caplog.text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestLoadExclusionsEdgeCases:
    def test_string_value_wrapped(self, tmp_path: Path) -> None:
        """exclude = "cli" (string not list) → wraps in list."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = "cli"
        """)
        )
        assert load_exclusions(tmp_path) == {"cli"}

    def test_empty_list(self, tmp_path: Path) -> None:
        """exclude = [] → empty set."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = []
        """)
        )
        assert load_exclusions(tmp_path) == set()

    def test_corrupt_toml(self, tmp_path: Path) -> None:
        """Corrupt pyproject.toml → empty set (graceful)."""
        (tmp_path / "pyproject.toml").write_text("{{not valid toml!!")
        assert load_exclusions(tmp_path) == set()

    def test_mixed_valid_invalid(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Mix of valid strings and invalid entries."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "pkg"

            [tool.axm-init]
            exclude = ["cli", 42, "changelog"]
        """)
        )
        with caplog.at_level(logging.WARNING):
            result = load_exclusions(tmp_path)
        assert result == {"cli", "changelog"}
        assert "Invalid exclusion entry" in caplog.text
