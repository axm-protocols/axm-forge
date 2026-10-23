"""Tests for ``workspace.pytest_importmode`` (importlib selected via addopts)."""

from pathlib import Path

import pytest

from axm_init.checks.workspace import check_pytest_importmode

_HEADER = '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'


def _write_pytest_section(root: Path, body: str) -> None:
    (root / "pyproject.toml").write_text(f"{_HEADER}[tool.pytest.ini_options]\n{body}")


class TestPytestImportmode:
    """Tests for check_pytest_importmode."""

    @pytest.mark.parametrize(
        "body",
        [
            'addopts = "--import-mode=importlib"\n',
            'addopts = "-q --import-mode=importlib"\n',
            'addopts = "-q --import-mode importlib -ra"\n',
            'addopts = ["--import-mode=importlib"]\n',
            'addopts = ["-q", "--import-mode", "importlib"]\n',
            'addopts = "--import-mode=prepend --import-mode=importlib"\n',
        ],
        ids=[
            "string",
            "string-with-other-flags",
            "string-two-token",
            "list",
            "list-two-token",
            "last-occurrence-wins",
        ],
    )
    def test_importmode_present(self, tmp_path: Path, body: str) -> None:
        """addopts selecting importlib (any supported form) passes."""
        _write_pytest_section(tmp_path, body)
        result = check_pytest_importmode(tmp_path)
        assert result.passed
        assert result.name == "workspace.pytest_importmode"

    def test_importmode_missing(self, ws_root: Path) -> None:
        """No import-mode configuration → fails."""
        result = check_pytest_importmode(ws_root)
        assert not result.passed
        assert "importlib" in result.message
        assert "No --import-mode in addopts" in result.details

    def test_addopts_without_importmode_fails(self, tmp_path: Path) -> None:
        """addopts present but without --import-mode → fails."""
        _write_pytest_section(tmp_path, 'addopts = "-q"\n')
        result = check_pytest_importmode(tmp_path)
        assert not result.passed

    @pytest.mark.parametrize(
        "body",
        [
            'addopts = "--import-mode=prepend"\n',
            'addopts = ["--import-mode", "append"]\n',
            'addopts = "--import-mode=importlib --import-mode=prepend"\n',
        ],
        ids=["prepend", "append-two-token", "last-occurrence-wins"],
    )
    def test_other_mode_fails(self, tmp_path: Path, body: str) -> None:
        """A different (or finally overridden) import mode → fails."""
        _write_pytest_section(tmp_path, body)
        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert any("Current import mode" in d for d in result.details)

    @pytest.mark.parametrize("key", ["import_mode", "importmode"])
    def test_bogus_key_fails(self, tmp_path: Path, key: str) -> None:
        """The non-existent ini key is not accepted, even alone."""
        _write_pytest_section(tmp_path, f'{key} = "importlib"\n')
        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert key in result.message
        assert "Remove" in result.fix

    def test_bogus_key_fails_even_with_addopts(self, tmp_path: Path) -> None:
        """Bogus key triggers a pytest warning, so it fails despite addopts."""
        _write_pytest_section(
            tmp_path,
            'import_mode = "importlib"\naddopts = "--import-mode=importlib"\n',
        )
        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert "ignores" in result.details[0]

    def test_invalid_addopts_quoting_fails(self, tmp_path: Path) -> None:
        """Unparseable addopts string does not crash and fails."""
        _write_pytest_section(tmp_path, 'addopts = "--import-mode=importlib \'"\n')
        result = check_pytest_importmode(tmp_path)
        assert not result.passed


class TestPytestImportmodeNoToml:
    """No pyproject.toml at root."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message
