"""Unit tests for ``check_precommit_installed`` fix-message wording."""

from pathlib import Path

from axm_init.checks.tooling import check_precommit_installed


class TestCheckPrecommitInstalledFixMessage:
    def test_install_fix_message_mentions_prek(self, tmp_path: Path) -> None:
        """AC4: the install-hint suggests ``prek install`` (uv-native runner).

        Config present but hooks not activated -> FAIL with a fix string that
        steers the user to ``prek install`` rather than the legacy
        ``pre-commit install``.
        """
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
        assert "prek install" in r.fix
