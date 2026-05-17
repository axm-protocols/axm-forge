from __future__ import annotations

from pathlib import Path

import pytest

from axm_smelt.cli import _read_input, check, compact


class TestCliUnit:
    def test_compact_invalid_preset(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """compact with an unknown preset prints to stderr and exits 1."""
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hello world"))
        with pytest.raises(SystemExit, match="1"):
            compact(preset="bad")
        assert "Unknown preset" in capsys.readouterr().err

    def test_compact_unknown_strategy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """compact with an unknown strategy prints to stderr and exits 1."""
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hello world"))
        with pytest.raises(SystemExit, match="1"):
            compact(strategies="nope")
        assert "Unknown strategy" in capsys.readouterr().err

    def test_compact_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        """compact with a nonexistent file prints to stderr and exits 1."""
        with pytest.raises(SystemExit, match="1"):
            compact(file=Path("/nonexistent"))
        assert "No such file" in capsys.readouterr().err

    def test_check_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        """check with a nonexistent file prints to stderr and exits 1."""
        with pytest.raises(SystemExit, match="1"):
            check(file=Path("/nonexistent"))
        assert "No such file" in capsys.readouterr().err

    def test_count_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        """count with a nonexistent file prints to stderr and exits 1."""
        from axm_smelt.cli import count

        with pytest.raises(SystemExit, match="1"):
            count(file=Path("/nonexistent"))
        assert "No such file" in capsys.readouterr().err

    def test_empty_string_preset(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An empty-string preset is either ignored or produces a clear error."""
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hello world"))
        # Empty preset should either work (treated as None) or give a clear error
        try:
            compact(preset="")
        except SystemExit as exc:
            assert exc.code == 1
            assert "preset" in capsys.readouterr().err.lower()

    def test_multiple_errors_file_wins(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When both file and preset are bad, file error surfaces first."""
        with pytest.raises(SystemExit, match="1"):
            compact(file=Path("/missing"), preset="bad")
        err = capsys.readouterr().err
        assert "No such file" in err

    def test_read_input_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_read_input with nonexistent path prints to stderr and exits 1."""
        with pytest.raises(SystemExit, match="1"):
            _read_input(Path("/nonexistent"))
        assert "No such file" in capsys.readouterr().err

    def test_no_traceback_on_missing_file(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ensure no Python traceback leaks to the user."""
        with pytest.raises(SystemExit):
            compact(file=Path("/nonexistent"))
        err = capsys.readouterr().err
        assert "Traceback" not in err
        assert "No such file" in err


# --- merged from test_version.py (package public-API surface tests; __init__.py
# and _version.py are exempt from the 1:1 mirror and have no canonical test
# location, so they live alongside the CLI public-surface tests) ---


class TestVersionUnit:
    def test_version_importable(self) -> None:
        from axm_smelt import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_public_api_exports(self) -> None:
        import axm_smelt

        assert hasattr(axm_smelt, "__all__")
        assert "__version__" in axm_smelt.__all__
