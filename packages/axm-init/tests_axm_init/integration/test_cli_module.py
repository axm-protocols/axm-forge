"""Split from ``test_cli_subcommands.py``."""


class TestNoTyperDependency:
    """Verify the cli module does not import typer (real file read)."""

    def test_no_typer_dependency(self) -> None:
        """typer should not be importable from cli module."""
        import axm_init.cli as cli_module

        source = open(cli_module.__file__).read()
        assert "import typer" not in source
        assert "from typer" not in source
