"""Unit tests for the Node structure rule (package.json + tsconfig)."""

from __future__ import annotations

import json
from pathlib import Path

from axm_audit.core.rules.node.structure import NodeStructureRule
from axm_audit.models.results import CheckResult


def _missing(result: CheckResult) -> list[str]:
    """Extract the ``missing`` list from a structure check result, typed."""
    missing = result.details["missing"]
    assert isinstance(missing, list)
    return missing


_COMPLETE_PKG = {"name": "x", "version": "0.1.0", "license": "MIT", "type": "module"}
_STRICT_TSCONFIG = {"compilerOptions": {"strict": True}}


def _write(
    tmp_path: Path,
    pkg: dict[str, object],
    tsconfig: dict[str, object] | None,
) -> None:
    """Write package.json (+ optional tsconfig.json) into *tmp_path*."""
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    if tsconfig is not None:
        (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig))


def test_complete_passes(tmp_path: Path) -> None:
    """A complete manifest + strict tsconfig scores 100."""
    _write(tmp_path, _COMPLETE_PKG, _STRICT_TSCONFIG)
    result = NodeStructureRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100


def test_missing_package_field_fails(tmp_path: Path) -> None:
    """A missing required field is reported and deducts points."""
    incomplete = {"name": "x", "version": "0.1.0"}  # no license, no type
    _write(tmp_path, incomplete, _STRICT_TSCONFIG)
    result = NodeStructureRule().check(tmp_path)
    assert result.passed is False
    assert "license" in _missing(result)
    assert "type" in _missing(result)


def test_non_strict_tsconfig_flagged(tmp_path: Path) -> None:
    """A tsconfig without strict mode is flagged."""
    _write(tmp_path, _COMPLETE_PKG, {"compilerOptions": {"strict": False}})
    result = NodeStructureRule().check(tmp_path)
    assert "strict" in _missing(result)


def test_no_package_json_fails(tmp_path: Path) -> None:
    """No package.json is a hard fail."""
    result = NodeStructureRule().check(tmp_path)
    assert result.passed is False
    assert result.score == 0
