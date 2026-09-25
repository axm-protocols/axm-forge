"""Cross-kind serialization of scaffold writes on one target root.

Learning profiles (written by the installed provider) and protocol profiles
(written by Forge) both read-modify-write the same ``pyproject.toml``. A
provider that takes Forge's exported ``target_root_lock`` shares one lock
registry keyed by canonical root with Forge, so a concurrent pair aimed at one
root serialises instead of losing the first writer's table.
"""

from __future__ import annotations

import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from axm_init.core.learning_profile import register_learning_profile
from axm_init.core.protocol_scaffolder import register_protocol_profile
from tests_axm_init._learning_provider import FakeLearningProvider

_METADATA = '[project]\nname = "example"\nversion = "0.1.0"\n'


def _root(parent: Path, name: str) -> Path:
    root = parent / name
    root.mkdir()
    (root / "pyproject.toml").write_text(_METADATA, encoding="utf-8")
    return root


def _profiles(root: Path) -> dict[str, Any]:
    document: dict[str, Any] = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    profiles = document["tool"]["axm-init"]
    assert isinstance(profiles, dict)
    return profiles


@pytest.mark.integration
def test_cross_kind_registrations_on_one_root_keep_both_profiles(
    tmp_path: Path,
    mocker: Any,
    fake_learning_provider: FakeLearningProvider,
) -> None:
    """AC1: a learning write and a protocol write on one root exclude each other.

    The learning critical section is widened past the moment the protocol
    thread is launched and has had its chance to run. Were the two kinds
    holding separate locks, the protocol registration would enter that
    window, read the pre-learning metadata and write it back without the
    learning table -- the lost update the shared lock exists to prevent.
    """
    root = _root(tmp_path, "target")
    protocol_may_run = threading.Event()
    original_merge = fake_learning_provider.merge_learning_metadata

    def merge_then_linger(*args: Any, **kwargs: Any) -> str:
        merged = original_merge(*args, **kwargs)
        # Still inside the learning lock: hand the protocol thread its window.
        protocol_may_run.set()
        threading.Event().wait(0.3)
        return merged

    mocker.patch.object(
        fake_learning_provider,
        "merge_learning_metadata",
        side_effect=merge_then_linger,
    )

    def learning() -> None:
        register_learning_profile(root, domain="vision", module_name="axm_demo")

    def protocol() -> None:
        assert protocol_may_run.wait(timeout=5.0)
        register_protocol_profile(root, domain="dev")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(learning), pool.submit(protocol)]
        for future in futures:
            future.result(timeout=30.0)

    # Neither writer clobbered the other: both tables survived.
    profiles = _profiles(root)
    assert profiles["learning"]["domain"] == "vision"
    assert profiles["protocols"]["domain"] == "dev"
