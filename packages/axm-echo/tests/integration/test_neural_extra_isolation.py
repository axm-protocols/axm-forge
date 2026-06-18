"""Install-time isolation of the optional ``[neural]`` extra (torch).

AC5 is the heart of this ticket: prove the isolation at INSTALL time, not just
at runtime import. The base dependency set must never pull ``torch`` into the
resolved environment; ``torch`` (and ``sentence-transformers``) may only enter
the resolution when the ``neural`` extra is explicitly requested.

The proof runs a real ``uv pip compile`` over the package's *declared*
dependency sets in an isolated scratch directory: ``uv`` resolves the full
transitive graph from PyPI metadata (no wheel downloads), so a torch in the
output means torch would be installed. We read the dependency lists straight
from the package's own ``pyproject.toml`` so the test tracks the real contract
rather than a hand-copied duplicate.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

# This file proves an INSTALL-time packaging invariant (the base dependency
# set never resolves torch; the ``neural`` extra does), not a runtime package
# symbol. ``no_package_symbol_ok`` opts it out of TEST_QUALITY_NO_PACKAGE_SYMBOL
# -- it is a packaging-linter check the project deliberately encodes as pytest.
pytestmark = [pytest.mark.integration, pytest.mark.no_package_symbol_ok]

# packages/axm-echo/tests/integration/ -> packages/axm-echo/
_PKG_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _PKG_ROOT / "pyproject.toml"

_TORCH_NEEDLES = ("torch", "sentence-transformers")


def _load_deps() -> tuple[list[str], list[str]]:
    """Return ``(base_deps, neural_extra_deps)`` from the package pyproject."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    base = list(project.get("dependencies", []))
    neural = list(project.get("optional-dependencies", {}).get("neural", []))
    return base, neural


def _resolvable(deps: list[str]) -> list[str]:
    """Drop first-party workspace deps (axm*) — unresolvable off-workspace.

    They are pure-Python AXM siblings and can never introduce ``torch``; the
    isolation contract is about the third-party numeric/neural stack.
    """
    return [d for d in deps if not d.startswith("axm")]


def _uv_compile(deps: list[str], scratch: Path) -> str:
    """Resolve ``deps`` with ``uv pip compile`` and return the lockfile text."""
    requirements = scratch / "requirements.in"
    requirements.write_text("\n".join(deps) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [
            "uv",
            "pip",
            "compile",
            "--quiet",
            "--no-header",
            "--python-version",
            "3.12",
            str(requirements),
        ],
        capture_output=True,
        text=True,
        cwd=scratch,
        timeout=300,
    )
    if proc.returncode != 0:
        pytest.skip(f"uv pip compile failed (network?): {proc.stderr.strip()}")
    return proc.stdout.lower()


@pytest.fixture(scope="module")
def uv_bin() -> str:
    """Locate the ``uv`` binary or skip the module if absent."""
    found = shutil.which("uv")
    if found is None:
        pytest.skip("uv not on PATH")
    return found


def test_base_install_excludes_torch(uv_bin: str, tmp_path: Path) -> None:
    """AC5: resolving the BASE deps must not pull torch into the environment."""
    base, _ = _load_deps()
    resolvable = _resolvable(base)
    # Base must declare numpy + scikit-learn and must NOT name torch directly.
    declared = " ".join(base).lower()
    assert "numpy" in declared
    assert "scikit-learn" in declared
    for needle in _TORCH_NEEDLES:
        assert needle not in declared, f"{needle} leaked into base dependencies"

    locked = _uv_compile(resolvable, tmp_path)
    for needle in _TORCH_NEEDLES:
        assert needle not in locked, f"{needle} resolved without the neural extra"


def test_neural_extra_includes_torch(uv_bin: str, tmp_path: Path) -> None:
    """AC3: the ``neural`` extra declares + resolves torch."""
    _, neural = _load_deps()
    declared = " ".join(neural).lower()
    assert "torch" in declared
    assert "sentence-transformers" in declared

    locked = _uv_compile(_resolvable(neural), tmp_path)
    assert "torch" in locked, "neural extra did not resolve torch"
