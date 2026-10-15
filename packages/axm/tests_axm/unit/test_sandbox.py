"""Write confinement: sandbox profiles and the environment allow-list."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm.sandbox import (
    INHERITED_ENV,
    UNCONFINED,
    Confinement,
    bubblewrap_argv,
    confinement,
    darwin_profile,
    inherited_environment,
)

EXPORT = Path("/private/tmp/axm-sandbox-x")
SCRATCH = Path("/private/tmp/axm-sandbox-y")
JUDGED = Path("/private/tmp/repo")


def test_the_darwin_profile_denies_every_write_but_the_writable_dirs() -> None:
    profile = darwin_profile([EXPORT, SCRATCH], [JUDGED])

    assert profile.startswith("(version 1)(allow default)(deny file-write*)")
    assert (
        f'(allow file-write* (subpath "{EXPORT}") (subpath "{SCRATCH}") '
        '(literal "/dev/null")'
    ) in profile


def test_a_protected_tree_is_denied_last_so_it_wins() -> None:
    profile = darwin_profile([EXPORT], [JUDGED])

    assert profile.endswith(f'(deny file-write* (subpath "{JUDGED}"))')
    assert profile.index("(allow file-write*") < profile.index(str(JUDGED))


def test_a_quote_in_a_path_cannot_break_the_profile() -> None:
    profile = darwin_profile([Path('/tmp/a"b')])

    assert '"/private/tmp/a\\"b"' in profile or '"/tmp/a\\"b"' in profile


def test_bubblewrap_binds_the_root_read_only_and_each_writable_dir() -> None:
    argv = bubblewrap_argv("/usr/bin/bwrap", [EXPORT, SCRATCH])

    assert argv[:5] == ("/usr/bin/bwrap", "--die-with-parent", "--ro-bind", "/", "/")
    assert argv[8:11] == ("--bind", str(EXPORT.resolve()), str(EXPORT.resolve()))
    assert argv[11:14] == ("--bind", str(SCRATCH.resolve()), str(SCRATCH.resolve()))
    assert argv[-1] == "--"


def test_bubblewrap_remounts_protected_paths_after_all_writable_binds() -> None:
    judged = EXPORT / "judged"
    sealed = SCRATCH / "sealed"
    argv = bubblewrap_argv("/usr/bin/bwrap", [EXPORT, SCRATCH], [judged, sealed])

    assert argv[8:11] == ("--bind", str(EXPORT.resolve()), str(EXPORT.resolve()))
    assert argv[11:14] == ("--bind", str(SCRATCH.resolve()), str(SCRATCH.resolve()))
    assert argv[14:17] == ("--ro-bind", str(judged.resolve()), str(judged.resolve()))
    assert argv[17:20] == ("--ro-bind", str(sealed.resolve()), str(sealed.resolve()))
    assert argv[20] == "--"


def test_a_confinement_wraps_its_command() -> None:
    confined = Confinement(isolation="sandbox", prefix=("sbx", "-p", "profile"))

    assert confined.wrap(["python", "-c", "0"]) == [
        "sbx",
        "-p",
        "profile",
        "python",
        "-c",
        "0",
    ]
    assert UNCONFINED.wrap(["true"]) == ["true"]
    assert UNCONFINED.isolation == "detect-only"


def test_a_confinement_without_a_writable_dir_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one writable"):
        confinement([])


def test_only_the_allow_listed_variables_are_inherited() -> None:
    source = {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "FORCE_COLOR": "3",
        "PYTHONPATH": "/elsewhere",
        "AWS_SECRET_ACCESS_KEY": "secret",
    }

    assert inherited_environment(source) == {"PATH": "/usr/bin", "LANG": "C.UTF-8"}
    assert "HOME" not in INHERITED_ENV
