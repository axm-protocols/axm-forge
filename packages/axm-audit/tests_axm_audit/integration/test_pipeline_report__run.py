"""Split from ``test_extract_helpers__pipeline.py``."""

from axm_audit.core.fix import run
from axm_audit.core.fix.models import PipelineReport

_MISTIERED_IO_TEST = (
    "from pathlib import Path\n\n\n"
    "def test_writes_a_file(tmp_path):\n"
    "    p = tmp_path / 'x.txt'\n"
    "    p.write_text('hello')\n"
    "    assert p.read_text() == 'hello'\n"
)


def test_run_dry_run_does_not_mutate(make_test_pkg):
    """AC4: apply=False -> applied=False, iterations=1, source unchanged."""
    pkg = make_test_pkg({"tests/unit/test_io.py": _MISTIERED_IO_TEST})
    before = (pkg / "tests" / "unit" / "test_io.py").read_text()

    report = run(pkg, apply=False)

    assert isinstance(report, PipelineReport)
    assert report.applied is False
    assert report.iterations == 1
    assert (pkg / "tests" / "unit" / "test_io.py").read_text() == before
    assert not (pkg / "tests" / "integration" / "test_io.py").exists()
