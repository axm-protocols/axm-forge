"""Unit test for resolve_identity: no-config-file edge case."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.identity import resolve_identity


class TestResolveIdentityEdgeCases:
    def test_no_config_file_returns_none(self, monkeypatch):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: None)
        result = resolve_identity(Path("/any"))
        assert result is None
