from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


def test_execute_rename_moves_and_renames(tmp_path: Path) -> None:
    """AC1, AC5: rename moves the symbol to the target under its new name and
    rewrites callers to reference the new name."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.0.0"\n'
    )
    old = pkg / "old.py"
    old.write_text("def OldName():\n    return 1\n")
    new = pkg / "new.py"
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import OldName\n\nOldName()\n")

    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="OldName",
        from_file=str(old),
        to_file=str(new),
        rename='{"OldName":"NewName"}',
    )

    assert result.success is True, result.error
    assert "def NewName" in new.read_text()
    assert "OldName" not in old.read_text()
    assert "NewName" in caller.read_text()


def test_insert_after_places_block_after_anchor(tmp_path: Path) -> None:
    """AC1: the moved block is inserted right after the named anchor and before
    the symbol that originally followed the anchor in the target module."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef After():\n    return 2\n")

    move_symbols(src, tgt, ["Moved"], insert_after="Anchor")

    text = tgt.read_text()
    assert text.index("def Anchor") < text.index("def Moved") < text.index("def After")


def test_string_forward_ref_warns(tmp_path: Path) -> None:
    """AC1,AC2: moving `Foo` warns about a string annotation that references it."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert any("Foo" in w for w in plan.warnings)


def test_string_forward_ref_no_false_positive(tmp_path: Path) -> None:
    """AC4: a string annotation `\"FooBar\"` does not trigger a forward-ref warning
    when only `Foo` is moved."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "FooBar"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert not any("forward-reference" in w for w in plan.warnings)


def test_string_forward_ref_not_rewritten(tmp_path: Path) -> None:
    """AC3: detection-only — the literal string annotation is left untouched."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert '"Foo"' in plan.source_text_new


def test_forward_ref_warning_real_files(tmp_path: Path) -> None:
    """AC1: a real on-disk move surfaces a non-empty warning naming the symbol."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], workspace_root=tmp_path)

    assert plan.warnings
    assert any("Foo" in w for w in plan.warnings)


def test_all_sync_real_files(tmp_path: Path) -> None:
    """AC1,AC2: written files reflect the synced `__all__` after a real move."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "src_pkg.py"
    tgt = tmp_path / "tgt_pkg.py"
    src.write_text(
        '__all__ = ["Foo", "Bar"]\n\n'
        "def Foo():\n    return 1\n\n"
        "def Bar():\n    return 2\n",
    )
    tgt.write_text('__all__ = ["Existing"]\n\ndef Existing():\n    return 0\n')

    move_symbols(src, tgt, ["Foo"], workspace_root=tmp_path)

    source_after = src.read_text()
    target_after = tgt.read_text()
    assert '"Foo"' not in source_after
    assert '"Bar"' in source_after
    assert '"Foo"' in target_after
    assert '"Existing"' in target_after


def test_side_effect_decorator_dotted_warns(tmp_path: Path) -> None:
    """AC2, AC4: moving an ``@app.route("/x")`` fn warns, naming deco + symbol."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('import app\n\n\n@app.route("/x")\ndef handler():\n    return 1\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["handler"], dry_run=True)

    matching = [w for w in plan.warnings if "side-effect decorator" in w]
    assert matching, plan.warnings
    assert any("app.route" in w and "handler" in w for w in matching)


def test_side_effect_decorator_bare_warns(tmp_path: Path) -> None:
    """AC4: a bare whitelisted decorator (``@fixture``) emits a warning."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from pytest import fixture\n\n\n@fixture\ndef thing():\n    return 1\n"
    )
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["thing"], dry_run=True)

    assert any(
        "side-effect decorator" in w and "fixture" in w and "thing" in w
        for w in plan.warnings
    ), plan.warnings


def test_non_whitelisted_decorator_no_warn(tmp_path: Path) -> None:
    """AC5: a non-whitelisted decorator produces no side-effect warning."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "def deco(f):\n    return f\n\n\n@deco\ndef thing():\n    return 1\n"
    )
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["thing"], dry_run=True)

    assert not any("side-effect decorator" in w for w in plan.warnings), plan.warnings


def test_custom_side_effect_decorator_extension(tmp_path: Path) -> None:
    """AC3: a caller-supplied custom decorator extends the whitelist."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("import mylib\n\n\n@mylib.register\ndef thing():\n    return 1\n")
    tgt.write_text("")

    plan = move_symbols(
        src,
        tgt,
        ["thing"],
        dry_run=True,
        side_effect_decorators=frozenset({"mylib.register"}),
    )

    assert any(
        "side-effect decorator" in w and "mylib.register" in w and "thing" in w
        for w in plan.warnings
    ), plan.warnings


def test_side_effect_decorator_warning_real_files(tmp_path: Path) -> None:
    """AC2: real-file move surfaces the decorator warning on plan.warnings."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "app_routes.py"
    tgt = tmp_path / "tasks.py"
    src.write_text("import celery\n\n\n@celery.task\ndef do_work():\n    return 42\n")
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["do_work"], workspace_root=tmp_path)

    assert any(
        "side-effect decorator" in w and "celery.task" in w and "do_work" in w
        for w in plan.warnings
    ), plan.warnings
