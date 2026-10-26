"""Split from ``test_pytest_invocation_and_parsing.py``."""

from pathlib import Path

from axm_audit.core.pytest_env import PLUGIN_MODULE
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
        assert cmd[cmd.index("-p") + 1] == PLUGIN_MODULE
        assert f"--axm-report-file={tmp_path / 'r.json'}" in cmd
        assert not any(arg.startswith("--json-report") for arg in cmd)
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
        assert "--no-cov" in cmd
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


def _cov_targets(project: Path, tmp_path: Path) -> list[str]:
    """Return the ``--cov=`` targets built for *project* (bare ``--cov`` -> [])."""
    cmd = build_pytest_cmd(
        report_path=tmp_path / "r.json",
        coverage_path=tmp_path / "cov.json",
        files=None,
        markers=None,
        stop_on_first=False,
        project_path=project,
    )
    return [arg.split("=", 1)[1] for arg in cmd if arg.startswith("--cov=")]


def _write_member(root: Path, name: str, *, modules: tuple[str, ...] = ()) -> None:
    """Create ``packages/<name>`` with a pyproject and one src package per module."""
    member = root / "packages" / name
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    for module in modules or (name.replace("-", "_"),):
        package = member / "src" / module
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")


def _workspace(root: Path, *, extra: str = "", coverage: str = "") -> None:
    """Write a uv-workspace root manifest."""
    root.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n'
        f'[tool.uv.workspace]\nmembers = ["packages/*"]\n{extra}'
        f"{coverage}"
    )


class TestBuildPytestCmdCoverageSources:
    """``--cov`` targets: explicit config, workspace members, ``src``, nothing."""

    def test_explicit_source_wins(self, tmp_path: Path) -> None:
        _workspace(tmp_path, coverage='[tool.coverage.run]\nsource = ["lib"]\n')
        _write_member(tmp_path, "alpha")
        assert _cov_targets(tmp_path, tmp_path) == ["lib"]

    def test_explicit_source_pkgs_used(self, tmp_path: Path) -> None:
        _workspace(tmp_path, coverage='[tool.coverage.run]\nsource_pkgs = ["alpha"]\n')
        _write_member(tmp_path, "alpha")
        _write_member(tmp_path, "beta")
        assert _cov_targets(tmp_path, tmp_path) == ["alpha"]

    def test_empty_source_pkgs_derives_members(self, tmp_path: Path) -> None:
        """The legacy ``source_pkgs = []`` must not disable member derivation."""
        _workspace(tmp_path, coverage="[tool.coverage.run]\nsource_pkgs = []\n")
        _write_member(tmp_path, "alpha")
        assert _cov_targets(tmp_path, tmp_path) == ["packages/alpha/src/alpha"]

    def test_workspace_derives_globbed_members(self, tmp_path: Path) -> None:
        _workspace(tmp_path)
        _write_member(tmp_path, "beta-pkg")
        _write_member(tmp_path, "alpha", modules=("alpha", "alpha_extra"))
        assert _cov_targets(tmp_path, tmp_path) == [
            "packages/alpha/src/alpha",
            "packages/alpha/src/alpha_extra",
            "packages/beta-pkg/src/beta_pkg",
        ]

    def test_workspace_honours_exclude(self, tmp_path: Path) -> None:
        _workspace(tmp_path, extra='exclude = ["packages/skip"]\n')
        _write_member(tmp_path, "alpha")
        _write_member(tmp_path, "skip")
        assert _cov_targets(tmp_path, tmp_path) == ["packages/alpha/src/alpha"]

    def test_member_without_init_measures_src_dir(self, tmp_path: Path) -> None:
        _workspace(tmp_path)
        member = tmp_path / "packages" / "solo"
        (member / "src").mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "solo"\n')
        assert _cov_targets(tmp_path, tmp_path) == ["packages/solo/src"]

    def test_member_without_src_is_skipped(self, tmp_path: Path) -> None:
        _workspace(tmp_path)
        _write_member(tmp_path, "alpha")
        flat = tmp_path / "packages" / "flat"
        flat.mkdir()
        (flat / "pyproject.toml").write_text('[project]\nname = "flat"\n')
        assert _cov_targets(tmp_path, tmp_path) == ["packages/alpha/src/alpha"]

    def test_non_workspace_falls_back_to_src(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "p"\n')
        (tmp_path / "src").mkdir()
        assert _cov_targets(tmp_path, tmp_path) == ["src"]

    def test_nothing_yields_bare_cov(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "p"\n')
        cmd = build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=tmp_path / "cov.json",
            files=None,
            markers=None,
            stop_on_first=False,
            project_path=tmp_path,
        )
        assert "--cov" in cmd
        assert not any(arg.startswith("--cov=") for arg in cmd)
