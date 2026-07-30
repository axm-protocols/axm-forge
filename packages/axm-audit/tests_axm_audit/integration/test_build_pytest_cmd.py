"""Split from ``test_pytest_invocation_and_parsing.py``."""

from pathlib import Path

from axm_audit.core.test_runner import build_pytest_cmd


class TestBuildPytestCmd:
    def test_basic_cmd(self, tmp_path: Path) -> None:
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "pytest" in cmd
        assert "--json-report" in cmd
        assert "-x" not in cmd

    def test_stop_on_first(self, tmp_path: Path) -> None:
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=None,
            stop_on_first=True,
        )
        assert "-x" in cmd

    def test_with_files(self, tmp_path: Path) -> None:
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=["tests/test_a.py", "tests/test_b.py"],
            markers=None,
            stop_on_first=False,
        )
        assert "tests/test_a.py" in cmd
        assert "tests/test_b.py" in cmd

    def test_with_markers(self, tmp_path: Path) -> None:
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=["not slow", "unit"],
            stop_on_first=False,
        )
        assert "-m" in cmd
        assert "not slow or unit" in cmd

    def test_with_coverage(self, tmp_path: Path) -> None:
        cov_path = tmp_path / "cov.json"
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=cov_path,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" in cmd
        assert f"--cov-report=json:{cov_path}" in cmd


class TestBuildPytestCmdCoverageWithFiles:
    """Unit tests: _build_pytest_cmd must omit --cov when coverage_path is None."""

    def test_build_pytest_cmd_no_cov_when_files(self, tmp_path: Path) -> None:
        cmd = build_pytest_cmd(
            report_path=tmp_path / "report.json",
            coverage_path=None,
            files=["t.py"],
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" not in cmd
        assert not any(arg.startswith("--cov-report") for arg in cmd)

    def test_build_pytest_cmd_cov_when_no_files(self, tmp_path: Path) -> None:
        cov_path = Path("/tmp/c.json")
        cmd = build_pytest_cmd(
            report_path=tmp_path / "report.json",
            coverage_path=cov_path,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" in cmd
        assert any(arg.startswith("--cov-report=json:") for arg in cmd)
