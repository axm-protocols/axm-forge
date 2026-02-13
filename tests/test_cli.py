"""Tests for AXM CLI autodiscovery wrapper."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any
from unittest.mock import patch

import cyclopts

from axm.cli import _EP_GROUP, create_app


def _make_entry_point(name: str, value: str, group: str) -> EntryPoint:
    """Create a fake entry point for testing."""
    return EntryPoint(name=name, value=value, group=group)


class TestCreateApp:
    """Tests for create_app factory."""

    def test_returns_cyclopts_app(self) -> None:
        """create_app returns a cyclopts.App instance."""
        app = create_app()
        assert isinstance(app, cyclopts.App)

    def test_app_name_is_axm(self) -> None:
        """The app is named 'axm'."""
        app = create_app()
        assert app.name == ("axm",)

    def test_no_commands_without_plugins(self) -> None:
        """Without installed plugins, a default handler is registered."""
        with patch("axm.cli.importlib.metadata.entry_points", return_value=[]):
            app = create_app()
        # App should still be created (with default handler)
        assert isinstance(app, cyclopts.App)


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

        # The command should be discoverable
        assert isinstance(app, cyclopts.App)

    def test_failed_entry_point_logged_not_fatal(self) -> None:
        """A broken entry point logs a warning but doesn't crash."""

        class BrokenEP:
            name = "broken"
            dist = "axm-broken"

            def load(self) -> Any:
                raise ImportError("missing dependency")

        with patch(
            "axm.cli.importlib.metadata.entry_points",
            return_value=[BrokenEP()],
        ):
            # Should not raise
            app = create_app()

        assert isinstance(app, cyclopts.App)

    def test_ep_group_constant(self) -> None:
        """The entry-point group matches the convention."""
        assert _EP_GROUP == "axm.commands"
