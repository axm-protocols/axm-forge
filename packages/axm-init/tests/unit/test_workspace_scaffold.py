"""Unit-level tests for workspace scaffold dispatch."""

from __future__ import annotations

from axm_init.core.templates import TemplateType, get_template_path


class TestTemplateTypeUnit:
    """TemplateType + get_template_path dispatch — pure value checks."""

    def test_standalone_explicit(self) -> None:
        path = get_template_path(TemplateType.STANDALONE)
        assert path.name == "python-project"
