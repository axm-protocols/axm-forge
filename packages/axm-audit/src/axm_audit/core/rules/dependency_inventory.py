"""Export the locked runtime dependency inventory without installing packages."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

from axm import session_dependency_environment


def _workspace_root(project: Path, uv: str, environment: dict[str, str]) -> Path:
    """Ask uv for the workspace root it will use to select the lock."""
    result = subprocess.run(  # noqa: S603 -- executable comes from the declared runtime
        [uv, "workspace", "dir", "--offline"],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "uv workspace discovery failed")
    lines = result.stdout.splitlines()
    if len(lines) != 1 or not Path(lines[0]).is_absolute():
        raise ValueError("uv workspace discovery returned an invalid root")
    root = Path(lines[0]).resolve()
    if not root.is_dir() or not project.is_relative_to(root):
        raise ValueError("uv workspace discovery returned an unrelated root")
    return root


def export_inventory(project: Path) -> tuple[str, dict[str, str]]:
    """Export the project's transitive third-party runtime dependencies."""
    project = project.resolve()
    try:
        metadata = tomllib.loads((project / "pyproject.toml").read_text())
        name = metadata["project"]["name"]
        if not isinstance(name, str) or not name:
            raise ValueError("missing project name")
        declared = session_dependency_environment(project)
        uv = (
            str(Path(declared.interpreter).parent / "uv")
            if declared is not None
            else shutil.which("uv")
        )
        if uv is None or not Path(uv).is_file():
            raise ValueError("declared uv instrument is missing")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}
        root = _workspace_root(project, uv, environment)
        lock = root / "uv.lock"
        if not lock.is_file():
            raise ValueError(f"uv.lock is missing from workspace root: {root}")
        lock_bytes = lock.read_bytes()
        locked = tomllib.loads(lock_bytes.decode())
        packages = locked.get("package", [])
        matches = [
            item
            for item in packages
            if isinstance(item, dict)
            and item.get("name") == name
            and isinstance(item.get("source"), dict)
            and any(
                isinstance(item["source"].get(kind), str)
                and (lock.parent / item["source"][kind]).resolve() == project
                for kind in ("editable", "virtual", "directory")
            )
        ]
        if len(matches) != 1:
            raise ValueError(f"project {name!r} is missing or ambiguous in uv.lock")
        before = hashlib.sha256(lock_bytes).hexdigest()
        result = subprocess.run(  # noqa: S603 -- executable comes from the declared runtime
            [
                uv,
                "export",
                "--project",
                str(root),
                "--frozen",
                "--offline",
                "--no-dev",
                "--no-default-groups",
                "--no-emit-local",
                "--no-hashes",
                "--no-header",
                "--no-annotate",
                "--package",
                name,
            ],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            raise ValueError(result.stderr.strip() or "uv export failed")
        if hashlib.sha256(lock.read_bytes()).hexdigest() != before:
            raise ValueError("uv.lock changed during export")
        inventory = result.stdout
        return inventory, {
            "project": name,
            "lock_path": str(lock),
            "lock_sha256": before,
            "inventory_sha256": hashlib.sha256(inventory.encode()).hexdigest(),
            "scope": "locked third-party runtime dependencies",
            "mode": "locked-runtime",
            "freshness": "not verified",
        }
    except (OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"dependency inventory unavailable: {exc}") from exc
