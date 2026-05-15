"""Tests for AXM CLI autodiscovery wrapper."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any
from unittest.mock import patch

import pytest

from axm.cli import _EP_GROUP, create_app


def _make_entry_point(name: str, value: str, group: str) -> EntryPoint:
    """Create a fake entry point for testing."""
    return EntryPoint(name=name, value=value, group=group)


class TestCreateApp:
    """Tests for create_app factory."""

    def test_returns_callable_app_with_help_text(self) -> None:
        """create_app returns an app whose help text identifies AXM."""
        app = create_app()
        assert app.help == "AXM — Protocol execution ecosystem."
        assert callable(app)

    def test_app_name_is_axm(self) -> None:
        """The app is named 'axm'."""
        app = create_app()
        assert app.name == ("axm",)

    def test_no_commands_without_plugins(self) -> None:
        """Without installed plugins, the no-commands fallback is registered."""
        with patch("axm.cli.importlib.metadata.entry_points", return_value=[]):
            app = create_app()
        assert app.default_command is not None
        assert app.default_command.__name__ == "_no_commands"

    def test_no_commands_handler_exits(self) -> None:
        """The no-commands fallback writes to stderr and exits."""

        with patch("axm.cli.importlib.metadata.entry_points", return_value=[]):
            app = create_app()

        # Find and invoke the _no_commands handler
        with pytest.raises(SystemExit) as exc_info:
            app([], exit_on_error=False)

        assert exc_info.value.code == 1


class TestAutodiscovery:
    """Tests for entry-point autodiscovery."""

    def test_discovers_command(self) -> None:
        """A valid entry point is registered as a command."""

        def fake_command() -> None:
            """A fake command."""

        class FakeEP:
            name = "fake"
            dist = "axm-fake"

            def load(self) -> Any:
                return fake_command

        with patch(
            "axm.cli.importlib.metadata.entry_points",
            return_value=[FakeEP()],
        ):
            app = create_app()

        registered_names = list(app)
        assert "fake" in registered_names

    def test_failed_entry_point_logged_not_fatal(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A broken entry point logs a warning and falls back to no-commands."""

        class BrokenEP:
            name = "broken"
            dist = "axm-broken"

            def load(self) -> Any:
                raise ImportError("missing dependency")

        with (
            caplog.at_level("WARNING", logger="axm.cli"),
            patch(
                "axm.cli.importlib.metadata.entry_points",
                return_value=[BrokenEP()],
            ),
        ):
            app = create_app()

        assert any(
            "broken" in record.message and record.levelname == "WARNING"
            for record in caplog.records
        )
        assert app.default_command is not None
        assert app.default_command.__name__ == "_no_commands"

    def test_ep_group_constant(self) -> None:
        """The entry-point group matches the convention."""
        assert _EP_GROUP == "axm.commands"
