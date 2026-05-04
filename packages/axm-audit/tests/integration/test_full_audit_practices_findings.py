from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_pkg"
    src = project / "src" / "sample_pkg"
    src.mkdir(parents=True)
    tests = project / "tests"
    tests.mkdir()

    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text(
        "import time\n"
        "\n"
        "def public_no_doc(x):\n"
        "    return x\n"
        "\n"
        "def safe():\n"
        "    try:\n"
        "        return 1\n"
        "    except:\n"
        "        return 0\n"
        "\n"
        "async def slow():\n"
        "    time.sleep(1)\n"
    )
    return project


def test_full_audit_practices_findings(sample_project: Path) -> None:
    from axm_audit.core.auditor import audit_project

    result = audit_project(sample_project)
    by_id = {c.rule_id: c for c in result.checks}

    expected = {
        "PRACTICE_DOCSTRING",
        "PRACTICE_BARE_EXCEPT",
        "PRACTICE_BLOCKING_IO",
        "PRACTICE_TEST_MIRROR",
    }
    assert expected <= set(by_id.keys()), (
        f"missing practice rules: {expected - set(by_id.keys())}"
    )
