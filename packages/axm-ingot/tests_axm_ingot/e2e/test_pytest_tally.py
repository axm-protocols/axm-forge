from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_public_symbol_reachable_black_box() -> None:
    """AC5: tally_outcomes is importable black-box from the package root.

    The subprocess prints a signature line that can ONLY be produced once
    ``tally_outcomes`` exists, is exported in ``__all__`` and classifies each
    recognised keyword plus the ``unknown`` bucket. Before the implementation
    lands, ``from axm_ingot import tally_outcomes`` raises inside the child, so
    stdout stays empty and the exact-match assertion fails (RED).
    """
    code = (
        "import axm_ingot\n"
        "from axm_ingot import tally_outcomes\n"
        "t = tally_outcomes(['FAILED z', 'ERROR y', 'SKIPPED w', 'garbage'])\n"
        "print('tally_outcomes' in axm_ingot.__all__, "
        "t['failed'], t['error'], t['skipped'], t['unknown'])\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "True 1 1 1 1", proc.stderr
    assert proc.returncode == 0, proc.stderr
