"""Unit-level tests for core/templates.py."""

from __future__ import annotations

from axm_init.core.templates import TemplateType, get_template_path


class TestGetTemplatePathUnit:
    """Tests for get_template_path() — pure value checks."""

    def test_path_is_python_project(self) -> None:
        """Returned path is the python-project template."""
        result = get_template_path()
        assert result.name == "python-project"


# --- TemplateType dispatch tests ---


class TestTemplateTypeUnit:
    """TemplateType + get_template_path dispatch — pure value checks."""

    def test_standalone_explicit(self) -> None:
        path = get_template_path(TemplateType.STANDALONE)
        assert path.name == "python-project"


# --- tests.* override relaxation tests ---


def _override_block(template_type: TemplateType) -> str:
    """Return the raw text following the mypy overrides marker."""
    raw = (get_template_path(template_type) / "pyproject.toml.jinja").read_text(
        encoding="utf-8"
    )
    marker = "[[tool.mypy.overrides]]"
    assert marker in raw
    return raw.split(marker, 1)[1]


class TestTestsOverrideRelaxation:
    """The tests.* override must relax disallow_incomplete_defs."""

    def test_python_project_relaxes_incomplete_defs(self) -> None:
        """python-project tests.* override declares the relaxation (AC1)."""
        block = _override_block(TemplateType.STANDALONE)
        assert 'module = ["tests.*"]' in block
        assert "disallow_incomplete_defs = false" in block

    def test_workspace_member_relaxes_incomplete_defs(self) -> None:
        """workspace-member tests.* override declares the relaxation (AC2)."""
        block = _override_block(TemplateType.MEMBER)
        assert "tests.*" in block
        assert "disallow_incomplete_defs = false" in block
