"""Discover uv members and select the CI matrix without installing the workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

from axm_ingot import resolve_workspace

__all__ = ["discover", "main", "select"]


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def discover(root: Path) -> list[dict[str, object]]:
    """Return validated, deterministic member metadata from the uv workspace."""
    workspace = resolve_workspace(root)
    if workspace is None or not workspace.members:
        raise ValueError("No uv workspace members found")
    members: list[dict[str, object]] = []
    names: set[str] = set()
    for member in workspace.members:
        relative = member.path.relative_to(root.resolve()).as_posix()
        data = tomllib.loads((member.path / "pyproject.toml").read_text())
        name = data["project"]["name"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise ValueError(f"Invalid project name: {name!r}")
        if _normalized(name) in names:
            raise ValueError(f"Duplicate project name: {name}")
        names.add(_normalized(name))
        project = data["project"]
        deps = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            deps.extend(extra)
        requirements = [
            _normalized(match.group())
            for dep in deps
            if (match := re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", dep))
        ]
        tests = (
            data.get("tool", {})
            .get("pytest", {})
            .get("ini_options", {})
            .get("testpaths", ["tests"])
        )
        if isinstance(tests, str):
            tests = tests.split()
        for test_path in tests:
            if Path(test_path).is_absolute() or ".." in Path(test_path).parts:
                raise ValueError(f"Test path must stay inside {name}: {test_path}")
        members.append(
            {
                "name": name,
                "path": relative,
                "tests": tests,
                "dependencies": requirements,
            }
        )
    return sorted(members, key=lambda item: str(item["name"]))


def select(
    members: list[dict[str, object]], changed: list[str] | None
) -> list[dict[str, object]]:
    """Select direct changes and transitive dependants, or all on shared changes."""
    if changed is None:
        return members
    selected: set[str] = set()
    for filename in changed:
        owners = [m for m in members if filename.startswith(str(m["path"]) + "/")]
        if not owners:
            # Root prose does not change Python behavior; infrastructure and
            # removed members do. Unknown paths fail safe to the full matrix.
            if filename.endswith(".md") or filename.startswith(("docs/", "assets/")):
                continue
            return members
        if "/templates/" in filename:
            return members
        selected.update(_normalized(str(m["name"])) for m in owners)
    while True:
        dependants = {
            _normalized(str(m["name"]))
            for m in members
            if selected.intersection(m["dependencies"])
        }
        expanded = selected | dependants
        if expanded == selected:
            break
        selected = expanded
    return [m for m in members if _normalized(str(m["name"])) in selected]


def _changed_paths(root: Path, event: dict[str, object]) -> list[str] | None:
    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        base = pull_request["base"]["sha"]
        merge_base = True
    else:
        base = event.get("before")
        merge_base = False
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", base):
        return None
    if set(base) == {"0"}:
        return None
    try:
        if merge_base:
            base = subprocess.check_output(
                ["git", "merge-base", base, "HEAD"], cwd=root, text=True
            ).strip()
        output = subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, "HEAD", "--"],
            cwd=root,
        )
    except subprocess.CalledProcessError:
        # Initial/shallow/force-pushed histories must not silently skip tests.
        return None
    return output.decode().split("\0")[:-1]


def main() -> None:
    """Write inventories and GitHub outputs for both workflows."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--event", type=Path)
    parser.add_argument(
        "--changed", type=Path, help="JSON path list for local validation"
    )
    args = parser.parse_args()
    root = args.root.resolve()
    members = discover(root)
    if args.changed:
        changed = json.loads(args.changed.read_text())
    else:
        event_path = args.event or (
            Path(os.environ["GITHUB_EVENT_PATH"])
            if os.getenv("GITHUB_EVENT_PATH")
            else None
        )
        event = json.loads(event_path.read_text()) if event_path else {}
        changed = _changed_paths(root, event)
    selected = select(members, changed)
    result = {"all": members, "packages": selected, "any": bool(selected)}
    print(json.dumps(result))
    if output := os.getenv("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"all={json.dumps(members)}\n")
            stream.write(f"packages={json.dumps(selected)}\n")
            stream.write(f"any={str(bool(selected)).lower()}\n")


if __name__ == "__main__":
    main()
