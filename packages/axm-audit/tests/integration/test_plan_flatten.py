"""Split from ``test_stages_plan.py``."""

from collections.abc import Callable
from pathlib import Path

from pytest_mock import MockerFixture

from axm_audit.core.fix.stages_plan import plan_flatten
from tests.integration._helpers import _PLAN_CHECK


def test_plan_flatten_emits_flatten_op_for_heterogeneous_class(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC6: benign heterogeneous Test* class → one FileOp(kind="flatten")."""
    pkg = make_pkg(
        pkg_name="mypkg",
        files={
            "src/mypkg/__init__.py": (
                "def foo() -> None:\n    pass\n\n"
                "def bar() -> None:\n    pass\n\n"
                '__all__ = ["foo", "bar"]\n'
            ),
            "tests/integration/test_x.py": (
                "from mypkg import foo, bar\n\n"
                "class TestX:\n"
                "    def test_one(self) -> None:\n"
                "        foo()\n"
                "    def test_two(self) -> None:\n"
                "        bar()\n"
            ),
        },
    )
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[{"verdict": "SPLIT", "path": str(abs_path)}],
    )
    ops = plan_flatten(pkg)
    flatten_ops = [op for op in ops if not op.rationale.startswith("PATHOLOGICAL")]
    assert len(flatten_ops) == 1
    assert flatten_ops[0].kind == "flatten"
    assert flatten_ops[0].source == abs_path


def test_plan_flatten_marks_pathological_class(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC6: heterogeneous class using self.x → op with PATHOLOGICAL rationale."""
    pkg = make_pkg(
        pkg_name="mypkg",
        files={
            "src/mypkg/__init__.py": (
                "def foo() -> None:\n    pass\n\n"
                "def bar() -> None:\n    pass\n\n"
                '__all__ = ["foo", "bar"]\n'
            ),
            "tests/integration/test_x.py": (
                "from mypkg import foo, bar\n\n"
                "class TestX:\n"
                "    def test_one(self) -> None:\n"
                "        self.x = 1\n"
                "        foo()\n"
                "    def test_two(self) -> None:\n"
                "        bar()\n"
            ),
        },
    )
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[{"verdict": "SPLIT", "path": str(abs_path)}],
    )
    ops = plan_flatten(pkg)
    assert any(op.rationale.startswith("PATHOLOGICAL") for op in ops)
