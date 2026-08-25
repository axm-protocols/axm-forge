"""Unit tests for the Node package.json gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.package_json import (
    check_package_json_exists,
    check_package_json_metadata,
)

_COMPLETE = {
    "name": "x",
    "version": "0.1.0",
    "license": "Apache-2.0",
    "repository": "git+https://github.com/org/x.git",
}


class TestCheckPackageJsonExists:
    """``check_package_json_exists`` over file states."""

    def test_missing_fails(self, tmp_path: Path) -> None:
        """No package.json fails the check."""
        result = check_package_json_exists(tmp_path)
        assert result.passed is False

    def test_present_and_valid_passes(self, tmp_path: Path) -> None:
        """A parsable package.json passes."""
        (tmp_path / "package.json").write_text(json.dumps(_COMPLETE))
        assert check_package_json_exists(tmp_path).passed is True

    def test_unparsable_fails(self, tmp_path: Path) -> None:
        """An existing but invalid package.json fails."""
        (tmp_path / "package.json").write_text("{not json")
        assert check_package_json_exists(tmp_path).passed is False


class TestCheckPackageJsonMetadata:
    """``check_package_json_metadata`` enforces required publication fields."""

    def test_complete_metadata_passes(self, tmp_path: Path) -> None:
        """All required fields present passes."""
        (tmp_path / "package.json").write_text(json.dumps(_COMPLETE))
        assert check_package_json_metadata(tmp_path).passed is True

    def test_missing_fields_fails_and_lists_them(self, tmp_path: Path) -> None:
        """Missing fields fail and the missing names are reported in details."""
        (tmp_path / "package.json").write_text('{"name":"x"}')
        result = check_package_json_metadata(tmp_path)
        assert result.passed is False
        joined = " ".join(result.details)
        assert "version" in joined
        assert "license" in joined
        assert "repository" in joined
