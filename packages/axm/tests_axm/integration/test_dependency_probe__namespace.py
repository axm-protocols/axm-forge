"""The metadata probe obeys lane import precedence for dotted package roots."""

import io
import json
import sys
from pathlib import Path

import pytest

from axm.tools._dependency_probe import main


def test_dotted_package_uses_the_lane_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "consumer"
    package.mkdir()
    package.joinpath("pyproject.toml").write_text(
        '[project]\nname="consumer"\nversion="0"\ndependencies=["external-api"]\n'
    )
    site = tmp_path / "site"
    original = site / "outer" / "inner"
    original.mkdir(parents=True)
    original.joinpath("__init__.py").write_text("ORIGINAL = True\n")
    dist = site / "external_api-1.dist-info"
    dist.mkdir()
    dist.joinpath("METADATA").write_text("Name: external-api\nVersion: 1\n")
    dist.joinpath("RECORD").write_text("outer/inner/__init__.py,,\n")
    lane = tmp_path / "lane-src"
    resolved = lane / "outer" / "inner"
    resolved.mkdir(parents=True)
    resolved.joinpath("__init__.py").write_text(
        'raise RuntimeError("dependency code must not run")\n'
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "package_root": str(package),
                    "pythonpath": [str(lane), str(site)],
                }
            )
        ),
    )
    main()
    assert ["outer.inner", str(resolved.resolve())] in json.loads(
        capsys.readouterr().out
    )
