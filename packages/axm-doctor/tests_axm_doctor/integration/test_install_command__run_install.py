"""Integration test for axm_doctor.install temp-file cleanup (real filesystem).

This exercises :func:`axm_doctor.install.run_install` against a real temp spool
directory (``tmp_path``) with ``tempfile.tempdir`` redirected, asserting nothing
is left behind on a failed download, so it lives at the integration level rather
than alongside the pure-stdlib unit install tests.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_doctor.detect import ToolStatus
from axm_doctor.install import InstallResult, install_command, run_install

pytestmark = pytest.mark.integration


def test_fetch_install_cleans_temp_on_download_error(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """AC1, AC2: a failed download leaves no temp file and yields a failed result.

    The uv installer fetches a script over HTTPS. When the download raises
    URLError, run_install must (1) leave no temp ``.sh`` file behind (fd closed,
    finally-cleanup), (2) return a failed InstallResult, and (3) NOT propagate
    the traceback.
    """
    import tempfile as _tempfile

    # Redirect tempfile so we can assert nothing is left behind by the failure.
    spool = tmp_path / "spool"
    spool.mkdir()
    mocker.patch.object(_tempfile, "tempdir", str(spool))

    # urlopen raises before any temp file would be consumed.
    mocker.patch(
        "axm_doctor.install.urllib.request.urlopen",
        side_effect=urllib.error.URLError("name resolution failed"),
    )
    # Never let a real subprocess fire even if the guard is wrong.
    run_spy = mocker.patch("axm_doctor.install.subprocess.run")
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="uv", state="absent"),
    )

    plan = install_command("uv")
    assert plan is not None
    assert plan.fetch_url is not None  # this is the script-installer path

    # No raw traceback escapes - run_install returns cleanly.
    result = run_install(plan, confirm=True)

    assert isinstance(result, InstallResult)
    assert result.returncode is not None
    assert result.returncode != 0  # failed state
    run_spy.assert_not_called()  # download failed before sh <tmpfile>
    # No temp file leaked into the spool dir.
    assert list(spool.iterdir()) == []
