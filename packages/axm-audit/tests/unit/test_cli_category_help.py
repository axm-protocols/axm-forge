from __future__ import annotations

import contextlib
import io

import pytest

from axm_audit.cli import app
from axm_audit.core.auditor import VALID_CATEGORIES


def _capture_help() -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with pytest.raises(SystemExit):
            app(["audit", "--help"])
    return buf.getvalue()


def test_cli_category_help_lists_all_valid_categories() -> None:
    help_text = _capture_help()
    missing = [cat for cat in VALID_CATEGORIES if cat not in help_text]
    assert not missing, f"--category help missing: {missing}\n---\n{help_text}"
