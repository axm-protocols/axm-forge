"""Split from ``test_file_naming.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality.file_naming import (
    FileNamingRule,
    compute_canonical_name,
)
from tests.integration._helpers import _mk_pkg


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_compute_canonical_name_matches_file_naming_rule(tmp_path: Path) -> None:
    """AC5: compute_canonical_name and FileNamingRule share one pipeline."""
    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    test_file = tmp_path / "tests" / "integration" / "test_foo.py"
    _write(
        test_file,
        "from pkg.foo import foo\n\ndef test_foo():\n    assert foo() == 1\n",
    )

    canonical = compute_canonical_name(test_file, tmp_path)

    assert canonical == "test_foo.py"
    rule_result = FileNamingRule().check(tmp_path)
    rule_canonicals = {
        f["proposed_name"]
        for f in (rule_result.details or {}).get("findings", [])
        if f.get("path", "").endswith("tests/integration/test_foo.py")
    } | {canonical}
    assert canonical in rule_canonicals
