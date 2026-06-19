"""Unit tests for ``axm_init.core.framework``."""

from __future__ import annotations

from pathlib import Path

from axm_init.core.framework import Framework, detect_framework


class TestDetectFramework:
    """``detect_framework`` selects the gold-standard check set."""

    def test_pyproject_only_is_python(self, tmp_path: Path) -> None:
        """A pyproject project detects as python."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        assert detect_framework(tmp_path) is Framework.PYTHON

    def test_empty_dir_defaults_python(self, tmp_path: Path) -> None:
        """No manifest defaults to python."""
        assert detect_framework(tmp_path) is Framework.PYTHON

    def test_package_json_is_node(self, tmp_path: Path) -> None:
        """A bare package.json detects as node."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        assert detect_framework(tmp_path) is Framework.NODE

    def test_svelte_dependency_is_svelte(self, tmp_path: Path) -> None:
        """A svelte dependency detects as svelte."""
        (tmp_path / "package.json").write_text(
            '{"name":"s","dependencies":{"svelte":"^5"}}'
        )
        assert detect_framework(tmp_path) is Framework.SVELTE
