"""Unit tests for axm_audit.core.fix.findings — finding ingestion + canonical names."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from axm_audit.core.fix.findings import (
    _absolutize_paths,
    _findings,
)


class _DictDetails(SimpleNamespace):
    """Minimal CheckResult-like stub with a ``details`` mapping."""


def test_findings_reads_details_dict() -> None:
    """_findings extracts the ``findings`` key from ``check.details``."""
    check = _DictDetails(details={"findings": [{"path": "a.py"}, {"path": "b.py"}]})
    assert _findings(check) == [{"path": "a.py"}, {"path": "b.py"}]


def test_findings_falls_back_to_findings_attr() -> None:
    """_findings reads ``check.findings`` when ``check.details`` lacks it."""
    check = SimpleNamespace(findings=[{"path": "x.py"}])
    assert _findings(check) == [{"path": "x.py"}]


def test_findings_returns_empty_when_no_source() -> None:
    """_findings returns [] when neither details nor findings exist."""
    assert _findings(SimpleNamespace()) == []


def test_findings_unwraps_pydantic_like_model() -> None:
    """_findings calls ``.model_dump()`` on items that expose it."""

    class _Model:
        def model_dump(self) -> dict[str, str]:
            return {"path": "m.py"}

    check = SimpleNamespace(details={"findings": [_Model()]})
    assert _findings(check) == [{"path": "m.py"}]


def test_findings_falls_back_to_vars() -> None:
    """_findings uses ``vars()`` for plain objects without model_dump."""

    class _Plain:
        def __init__(self) -> None:
            self.path = "p.py"

    check = SimpleNamespace(details={"findings": [_Plain()]})
    assert _findings(check) == [{"path": "p.py"}]


def test_absolutize_paths_rewrites_relative_path_key(tmp_path: Path) -> None:
    """_absolutize_paths joins relative path/test_file/files to project_path."""
    finding: dict[str, object] = {
        "path": "tests/test_x.py",
        "test_file": "tests/test_y.py",
        "files": ["tests/a.py", "tests/b.py"],
    }
    _absolutize_paths(finding, tmp_path)
    assert finding["path"] == str(tmp_path / "tests" / "test_x.py")
    assert finding["test_file"] == str(tmp_path / "tests" / "test_y.py")
    assert finding["files"] == [
        str(tmp_path / "tests" / "a.py"),
        str(tmp_path / "tests" / "b.py"),
    ]


def test_absolutize_paths_preserves_absolute_paths(tmp_path: Path) -> None:
    """_absolutize_paths leaves already-absolute paths unchanged."""
    abs_path = str(tmp_path / "tests" / "abs.py")
    finding: dict[str, object] = {"path": abs_path, "files": [abs_path]}
    _absolutize_paths(finding, tmp_path)
    assert finding["path"] == abs_path
    assert finding["files"] == [abs_path]


def test_absolutize_paths_skips_non_string_entries(tmp_path: Path) -> None:
    """_absolutize_paths leaves non-string file entries alone (defensive)."""
    finding: dict[str, object] = {"files": [42, None, "tests/a.py"]}
    _absolutize_paths(finding, tmp_path)
    files = finding["files"]
    assert isinstance(files, list)
    assert files[0] == 42
    assert files[1] is None
    assert files[2] == str(tmp_path / "tests" / "a.py")


def test_absolutize_paths_noop_when_keys_absent(tmp_path: Path) -> None:
    """_absolutize_paths leaves a dict without target keys unchanged."""
    finding: dict[str, object] = {"other": "value"}
    _absolutize_paths(finding, tmp_path)
    assert finding == {"other": "value"}
