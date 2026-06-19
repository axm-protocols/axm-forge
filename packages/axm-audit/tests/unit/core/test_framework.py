"""Unit tests for ``axm_audit.core.framework``."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.framework import (
    Framework,
    detect_framework,
    resolve_frameworks,
)


class TestDetectFramework:
    """``detect_framework`` reads manifest markers."""

    def test_pyproject_only_is_python(self, tmp_path: Path) -> None:
        """A pyproject.toml with no package.json detects as python."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        assert detect_framework(tmp_path) is Framework.PYTHON

    def test_empty_dir_defaults_to_python(self, tmp_path: Path) -> None:
        """No manifest at all falls back to the conservative python default."""
        assert detect_framework(tmp_path) is Framework.PYTHON

    def test_package_json_is_node(self, tmp_path: Path) -> None:
        """A package.json with no svelte marker detects as node."""
        (tmp_path / "package.json").write_text('{"name":"n"}')
        assert detect_framework(tmp_path) is Framework.NODE

    def test_package_json_with_svelte_dep_is_svelte(self, tmp_path: Path) -> None:
        """A package.json declaring svelte in devDependencies detects as svelte."""
        (tmp_path / "package.json").write_text(
            '{"name":"s","devDependencies":{"svelte":"^5"}}'
        )
        assert detect_framework(tmp_path) is Framework.SVELTE

    def test_svelte_config_file_is_svelte(self, tmp_path: Path) -> None:
        """A svelte.config.js next to package.json detects as svelte."""
        (tmp_path / "package.json").write_text('{"name":"s"}')
        (tmp_path / "svelte.config.js").write_text("export default {};")
        assert detect_framework(tmp_path) is Framework.SVELTE

    def test_unparsable_package_json_is_node(self, tmp_path: Path) -> None:
        """An invalid package.json still detects node (svelte marker unreadable)."""
        (tmp_path / "package.json").write_text("{not json")
        assert detect_framework(tmp_path) is Framework.NODE


class TestResolveFrameworks:
    """``resolve_frameworks`` expands a framework to its rule-set chain."""

    def test_python_resolves_to_itself(self) -> None:
        """Python runs only python rules."""
        assert resolve_frameworks(Framework.PYTHON) == (Framework.PYTHON,)

    def test_node_resolves_to_itself(self) -> None:
        """Node runs only node rules."""
        assert resolve_frameworks(Framework.NODE) == (Framework.NODE,)

    def test_svelte_inherits_node(self) -> None:
        """Svelte runs node rules first, then svelte-specific ones."""
        assert resolve_frameworks(Framework.SVELTE) == (
            Framework.NODE,
            Framework.SVELTE,
        )
