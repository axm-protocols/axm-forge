"""Tests for AXM CLI."""

from typer.testing import CliRunner

from axm_init.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "axm-init" in result.stdout


def test_init(tmp_path) -> None:
    """Test init command creates project."""
    result = runner.invoke(app, ["init", str(tmp_path), "--name", "test-proj"])
    assert result.exit_code == 0
    assert "test-proj" in result.stdout
