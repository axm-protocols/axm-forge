"""Export the locked runtime dependency inventory without installing packages."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

from axm import session_dependency_environment


def export_inventory(project: Path) -> tuple[str, dict[str, str]]:
    """Export the project's transitive third-party runtime dependencies."""
    project = project.resolve()
    try:
        metadata = tomllib.loads((project / "pyproject.toml").read_text())
        name = metadata["project"]["name"]
        if not isinstance(name, str) or not name:
            raise ValueError("missing project name")
        lock = next(
            (
                p / "uv.lock"
                for p in (project, *project.parents)
                if (p / "uv.lock").is_file()
            ),
            None,
        )
        if lock is None:
            raise ValueError("uv.lock is missing")
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
        declared = session_dependency_environment(project)
        uv = (
            str(Path(declared.interpreter).parent / "uv")
            if declared is not None
            else shutil.which("uv")
        )
        if uv is None or not Path(uv).is_file():
            raise ValueError("declared uv instrument is missing")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}
        result = subprocess.run(  # noqa: S603 -- executable comes from the declared runtime
            [
                uv,
                "export",
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
