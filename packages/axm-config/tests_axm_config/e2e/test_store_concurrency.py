"""Real-process races at the config-file boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from axm_config import NamespaceStore

pytestmark = pytest.mark.e2e

_WORKER = """
import pathlib, sys, time
from axm_config import NamespaceStore
from axm_config.store import _PinnedNamespaceStore
root, mode, token = sys.argv[1:]
# Slow the read/modify boundary to expose lost updates without the file lock.
load = _PinnedNamespaceStore._load_for_update
def slow(self):
    result = load(self)
    time.sleep(0.01)
    return result
_PinnedNamespaceStore._load_for_update = slow
gate = pathlib.Path(root) / "start"
deadline = time.monotonic() + 10
while not gate.exists():
    if time.monotonic() > deadline:
        raise RuntimeError("gate timeout")
    time.sleep(0.01)
store = NamespaceStore()
if mode == "cas":
    ok = store.compare_and_replace_section(
        "profile", {"revision": token}, expected={"revision": "0"}
    )
    print("winner" if ok else "conflict")
elif mode == "replace":
    for i in range(15):
        store.replace_section("second", {"counter": i})
else:
    for i in range(15):
        store.write("first", "key" + str(i), i)
        store.write("first", "temporary", i)
        store.delete("first", "temporary")
"""


def _race(tmp_path: Path, modes: tuple[str, str]) -> list[str]:
    # The package's autouse fixture already isolates HOME and removes AXM_*.
    env = dict(os.environ)
    source = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
    children = [
        subprocess.Popen(
            [sys.executable, "-c", _WORKER, str(tmp_path), mode, str(index + 1)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index, mode in enumerate(modes)
    ]
    try:
        (tmp_path / "start").write_text("go")
        output = []
        for child in children:
            stdout, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, stderr
            output.append(stdout.strip())
        return output
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()


def test_two_namespaces_survive_competing_write_delete_replace(tmp_path):
    _race(tmp_path, ("write", "replace"))
    store = NamespaceStore()
    assert store.read_exact("first") == {"key" + str(i): i for i in range(15)}
    assert store.read_exact("second") == {"counter": 14}


def test_same_revision_has_exactly_one_process_winner(tmp_path):
    store = NamespaceStore()
    store.write("profile", "revision", "0")
    assert sorted(_race(tmp_path, ("cas", "cas"))) == ["conflict", "winner"]
    assert store.read_exact("profile")["revision"] in {"1", "2"}
