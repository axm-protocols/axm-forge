from __future__ import annotations

from pathlib import Path


def test_gen_ref_pages_template_exists() -> None:
    """The gen_ref_pages.py template file exists at the expected location."""
    template = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "axm_init"
        / "templates"
        / "uv-workspace"
        / "docs"
        / "gen_ref_pages.py"
    )
    assert template.is_file(), f"Template not found: {template}"


def test_gen_ref_pages_template_is_valid_python() -> None:
    """The gen_ref_pages.py template compiles as valid Python."""
    template = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "axm_init"
        / "templates"
        / "uv-workspace"
        / "docs"
        / "gen_ref_pages.py"
    )
    source = template.read_text(encoding="utf-8")
    compile(source, str(template), "exec")
