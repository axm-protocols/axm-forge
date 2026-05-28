from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import MoveValidationError

pytestmark = pytest.mark.integration


def test_move_parse_error_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    original_source = "from __future__ import annotations\n\nclass Foo:\n    pass\n"
    original_target = "from __future__ import annotations\n"
    src.write_text(original_source)
    tgt.write_text(original_target)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    import axm_anvil.core.move as move_mod

    # Inject corruption by replacing text-rendering seam. The implementation
    # should validate post-render and raise MoveValidationError.
    real_code = cst_code_getter = None  # noqa: F841

    class _BrokenModule:
        code = "def :::broken(\n"

    def fake_render_source(*args: object, **kwargs: object) -> str:
        return "def :::broken(\n"

    # Try several known seam names; at least one must exist for this test
    # to be meaningful. If none match, the implementation has a different
    # seam and the test is expected to be revised alongside the impl.
    patched = False
    for name in (
        "_render_source",
        "_build_source_text",
        "_apply_remove",
        "_remove_and_render",
    ):
        if hasattr(move_mod, name):
            monkeypatch.setattr(move_mod, name, fake_render_source)
            patched = True
            break

    if not patched:
        # Fallback: patch libcst Module.code to return broken text for the
        # source render path. This is aggressive but guarantees the
        # validator sees unparseable output.
        import libcst as cst

        original_code = cst.Module.code.fget
        calls = {"n": 0}

        def broken_code(self):
            calls["n"] += 1
            if calls["n"] == 1:
                return "def :::broken(\n"
            return original_code(self)

        monkeypatch.setattr(cst.Module, "code", property(broken_code), raising=False)

    with pytest.raises(MoveValidationError):
        move_symbols(src, tgt, ["Foo"], dry_run=False)

    assert src.read_text() == original_source
    assert tgt.read_text() == original_target
