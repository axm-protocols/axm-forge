"""Filesystem verification of data-format syntax gates."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp, RewriteOp

pytestmark = pytest.mark.integration


class TestDataSyntaxGate:
    """Filesystem verification of data-format syntax gates."""

    @pytest.mark.parametrize("broken", [True, False])
    def test_toml_replace(self, tmp_path: Path, broken: bool) -> None:
        """Refuse broken TOML before writing, and apply valid replacements."""
        target = tmp_path / "pyproject.toml"
        before = b'[project]\nname = "old"\n'
        target.write_bytes(before)
        new = 'name = "new' if broken else 'name = "new"'
        result = batch_apply(
            tmp_path,
            [ReplaceOp(file=target.name, edits=[Edit(old='name = "old"', new=new)])],
        )
        assert result.success is not broken
        assert target.read_bytes() == (
            before if broken else b'[project]\nname = "new"\n'
        )
        if broken:
            assert result.details[0].file == target.name
            assert result.checkpoint is None

    @pytest.mark.parametrize("broken", [True, False])
    def test_json_rewrite(self, tmp_path: Path, broken: bool) -> None:
        """Refuse broken JSON before writing, and apply valid rewrites."""
        target = tmp_path / "settings.json"
        before = b'{"value": 1}\n'
        target.write_bytes(before)
        after = '{"value": }\n' if broken else '{"value": 2}\n'
        result = batch_apply(
            tmp_path,
            [
                RewriteOp(
                    file=target.name,
                    content=after,
                    expected_checksum=hashlib.sha256(before).hexdigest(),
                )
            ],
        )
        assert result.success is not broken
        assert target.read_bytes() == (before if broken else after.encode())
        if broken:
            assert result.details[0].file == target.name
            assert result.checkpoint is None
