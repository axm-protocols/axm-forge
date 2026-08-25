"""Split from ``test_private_import_detection.py``."""

from pathlib import Path


def test_render_helper_distinguishes_kinds_unit(tmp_path: Path) -> None:
    """Direct unit test of the renderer."""
    from axm_audit.core.rules.test_quality import private_imports as pi_mod

    render = pi_mod.__dict__["_render_private_imports_text"]
    findings = [
        {
            "test_file": str(tmp_path / "tests" / "test_a.py"),
            "line": 1,
            "import_module": "pkg.mod",
            "private_symbol": "_foo",
            "symbol_kind": "function",
            "access_kind": "import",
        },
        {
            "test_file": str(tmp_path / "tests" / "test_b.py"),
            "line": 5,
            "import_module": "pkg.mod",
            "private_symbol": "_m",
            "symbol_kind": "method",
            "access_kind": "attribute",
        },
    ]
    text = render(findings, tmp_path)
    assert "[import]" in text
    assert "[attribute]" in text
