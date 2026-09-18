from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.e2e

_FINAL_LOSS_PREFIX = "FINAL_LOSS="
_CODE_SUFFIXES = {".py", ".pyc", ".pyd", ".so"}
_DATA_SUFFIXES = {
    ".bin",
    ".cfg",
    ".csv",
    ".json",
    ".jsonl",
    ".npy",
    ".npz",
    ".pt",
    ".pth",
    ".safetensors",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
_SOCKET_BLOCKER = """
import socket


def _blocked_connection(*args, **kwargs):
    raise OSError("outbound sockets are disabled by the e2e test")


socket.socket.connect = _blocked_connection
socket.socket.connect_ex = _blocked_connection
socket.create_connection = _blocked_connection
"""
_AUDIT_HOOK = """
import os
import sys
from pathlib import Path

_AUDIT_LOG = os.environ.get("AXM_OPEN_AUDIT_LOG")
_AUDIT_BUSY = False


def _is_read_open(mode, flags):
    if isinstance(mode, str):
        return "r" in mode or "+" in mode
    if isinstance(flags, int):
        return flags & os.O_ACCMODE != os.O_WRONLY
    return False


def _record_read(event, args):
    global _AUDIT_BUSY
    if event != "open" or _AUDIT_BUSY or not _AUDIT_LOG:
        return
    path = args[0] if args else None
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if not isinstance(path, (str, bytes)) or not _is_read_open(mode, flags):
        return
    try:
        resolved = Path(os.fsdecode(path)).resolve(strict=False)
        _AUDIT_BUSY = True
        with open(_AUDIT_LOG, "a", encoding="utf-8") as stream:
            stream.write(str(resolved) + "\\n")
    except (OSError, TypeError, ValueError):
        return
    finally:
        _AUDIT_BUSY = False


sys.addaudithook(_record_read)
"""


@dataclass(frozen=True)
class GeneratedLearningProject:
    root: Path
    module_name: str
    python: Path | None
    site_packages: Path | None
    python_roots: tuple[Path, ...]
    setup_error: str | None


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _process_error(label: str, proc: subprocess.CompletedProcess[str]) -> str:
    return (
        f"{label} exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


def _is_exact_pin(reference: str) -> bool:
    requirement = reference.partition(";")[0].strip()
    return (
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^]]+\])?==[^\s=]+",
            requirement,
        )
        is not None
    )


@pytest.fixture(scope="module")
def learning_project(
    tmp_path_factory: pytest.TempPathFactory,
) -> GeneratedLearningProject:
    root = tmp_path_factory.mktemp("learning-project") / "generated"
    distribution = "learning-e2e"
    result = InitScaffoldTool().execute(
        path=str(root),
        name=distribution,
        org="axm-e2e",
        author="AXM E2E",
        email="e2e@example.invalid",
        private=True,
        kind="learning",
    )
    if not result.success:
        return GeneratedLearningProject(
            root, distribution.replace("-", "_"), None, None, (), result.error
        )

    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    references = tuple(metadata["project"]["dependencies"])
    if len(references) != 3 or not all(map(_is_exact_pin, references)):
        error = (
            "the generated pyproject must declare exactly three exact-pinned "
            f"learning dependencies; got {references!r}"
        )
        return GeneratedLearningProject(
            root, distribution.replace("-", "_"), None, None, (), error
        )

    venv = root / ".venv"
    created = _run(
        ["uv", "venv", "--python", sys.executable, str(venv)],
        cwd=root,
    )
    if created.returncode != 0:
        return GeneratedLearningProject(
            root,
            distribution.replace("-", "_"),
            None,
            None,
            (),
            _process_error("uv venv", created),
        )

    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    installed = _run(
        ["uv", "pip", "install", "--python", str(python), *references],
        cwd=root,
    )
    if installed.returncode != 0:
        return GeneratedLearningProject(
            root,
            distribution.replace("-", "_"),
            python,
            None,
            (),
            _process_error("uv pip install", installed),
        )

    paths = _run(
        [
            str(python),
            "-c",
            (
                "import json, sysconfig; "
                "print(json.dumps({k: sysconfig.get_path(k) "
                "for k in ('purelib', 'stdlib', 'platstdlib')}))"
            ),
        ],
        cwd=root,
    )
    if paths.returncode != 0:
        return GeneratedLearningProject(
            root,
            distribution.replace("-", "_"),
            python,
            None,
            (),
            _process_error("venv sysconfig", paths),
        )
    resolved_paths = json.loads(paths.stdout)
    return GeneratedLearningProject(
        root=root,
        module_name=distribution.replace("-", "_"),
        python=python,
        site_packages=Path(resolved_paths["purelib"]),
        python_roots=tuple(
            Path(resolved_paths[key]).resolve()
            for key in ("stdlib", "platstdlib")
            if resolved_paths[key]
        ),
        setup_error=None,
    )


def _require_runnable(project: GeneratedLearningProject) -> tuple[Path, Path]:
    assert project.setup_error is None, project.setup_error
    assert project.python is not None
    assert project.site_packages is not None
    return project.python, project.site_packages


def _install_sitecustomize(
    project: GeneratedLearningProject,
    source: str,
) -> None:
    _, site_packages = _require_runnable(project)
    (site_packages / "sitecustomize.py").write_text(
        textwrap.dedent(source), encoding="utf-8"
    )


def _run_training(
    project: GeneratedLearningProject,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    python, _ = _require_runnable(project)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(project.root / "src"),
        }
    )
    if extra_env:
        env.update(extra_env)
    return _run(
        [python.as_posix(), "-m", f"{project.module_name}.tools.train"],
        cwd=project.root,
        env=env,
    )


def _assert_finite_final_loss(proc: subprocess.CompletedProcess[str]) -> float:
    assert proc.returncode == 0, _process_error("training", proc)
    loss_lines = [
        line for line in proc.stdout.splitlines() if line.startswith(_FINAL_LOSS_PREFIX)
    ]
    assert len(loss_lines) == 1, (
        f"expected one {_FINAL_LOSS_PREFIX!r} line, got {loss_lines!r}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    loss = float(loss_lines[0].removeprefix(_FINAL_LOSS_PREFIX).strip())
    assert math.isfinite(loss), f"final loss is not finite: {loss!r}"
    return loss


def _is_below(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def test_generated_training_reports_finite_final_loss(
    learning_project: GeneratedLearningProject,
) -> None:
    """AC1: the isolated generated entry point reports one finite final loss."""
    _install_sitecustomize(learning_project, "# intentionally empty\n")

    proc = _run_training(learning_project)

    _assert_finite_final_loss(proc)


def test_generated_training_blocks_outbound_sockets(
    learning_project: GeneratedLearningProject,
) -> None:
    """AC2: the real generated training run succeeds with sockets disabled."""
    _install_sitecustomize(learning_project, _SOCKET_BLOCKER)

    proc = _run_training(learning_project)

    _assert_finite_final_loss(proc)


def test_generated_training_reads_data_only_from_project(
    learning_project: GeneratedLearningProject,
) -> None:
    """AC3: every observed non-code data read is contained by the project."""
    audit_log = learning_project.root / "training-open.log"
    _install_sitecustomize(learning_project, _SOCKET_BLOCKER + _AUDIT_HOOK)

    proc = _run_training(
        learning_project,
        extra_env={"AXM_OPEN_AUDIT_LOG": str(audit_log)},
    )

    _assert_finite_final_loss(proc)
    observed = {
        Path(line).resolve(strict=False)
        for line in audit_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    excluded_roots = (
        (learning_project.root / ".venv").resolve(),
        *learning_project.python_roots,
    )
    data_reads = {
        path
        for path in observed
        if path != audit_log.resolve()
        and not any(_is_below(path, root) for root in excluded_roots)
        and not any(part.endswith(".dist-info") for part in path.parts)
        and path.suffix.lower() not in _CODE_SUFFIXES
        and path.suffix.lower() in _DATA_SUFFIXES
    }
    assert data_reads, f"no project data read was observed; raw reads: {observed!r}"
    outside = {
        path
        for path in data_reads
        if not _is_below(path, learning_project.root.resolve())
    }
    assert not outside, f"training read data outside the project: {outside!r}"
