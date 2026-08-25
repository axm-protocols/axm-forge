"""Unit tests for the TypeScript backend.

Skipped entirely when the optional ``tree-sitter-typescript`` grammar is not
installed, so a Python-only environment does not fail on these.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_typescript")

from axm_ast.core.backends.typescript import TypeScriptBackend
from axm_ast.models.nodes import ClassKind, ModuleInfo

_SAMPLE = """\
import { foo } from "./util.js";

export function greet(name: string): string {
  return name;
}

export const add = (a: number, b: number): number => a + b;

async function load(): Promise<void> {}

export interface User { id: number; }
export type ID = string | number;
export enum Color { Red, Green }
export class Service { run(): void {} }
"""


def _module(tmp_path: Path) -> ModuleInfo:
    """Write the sample and extract its ModuleInfo via the TS backend."""
    src = tmp_path / "sample.ts"
    src.write_text(_SAMPLE)
    return TypeScriptBackend().extract_module(src)


def test_suffixes_and_name() -> None:
    """The TS backend owns .ts/.tsx."""
    backend = TypeScriptBackend()
    assert backend.suffixes == (".ts", ".tsx")
    assert backend.name == "typescript"


def test_extracts_named_and_arrow_functions(tmp_path: Path) -> None:
    """Both `function` declarations and arrow consts are extracted."""
    mod = _module(tmp_path)
    names = {f.name for f in mod.functions}
    assert {"greet", "add", "load"} <= names


def test_async_function_flagged(tmp_path: Path) -> None:
    """An async function is marked is_async."""
    mod = _module(tmp_path)
    load = next(f for f in mod.functions if f.name == "load")
    assert load.is_async is True


def test_return_type_captured(tmp_path: Path) -> None:
    """The TS return-type annotation is captured."""
    mod = _module(tmp_path)
    greet = next(f for f in mod.functions if f.name == "greet")
    assert greet.return_type == "string"


def test_class_like_kinds(tmp_path: Path) -> None:
    """interface/type/enum/class map to the right ClassKind."""
    mod = _module(tmp_path)
    by_name = {c.name: c.kind for c in mod.classes}
    assert by_name["User"] is ClassKind.INTERFACE
    assert by_name["ID"] is ClassKind.TYPE_ALIAS
    assert by_name["Color"] is ClassKind.ENUM
    assert by_name["Service"] is ClassKind.CLASS


def test_relative_import_detected(tmp_path: Path) -> None:
    """A ./-prefixed import source is marked relative with its named symbols."""
    mod = _module(tmp_path)
    imp = next(i for i in mod.imports if i.module == "./util.js")
    assert imp.is_relative is True
    assert "foo" in imp.names
