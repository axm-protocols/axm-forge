from __future__ import annotations

import importlib
import io

from pytest_mock import MockerFixture


class NonInteractiveStream(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_read_source_reads_non_interactive_stdin() -> None:
    """AC4: un flux non interactif est lu quand aucun chemin n'est désigné."""
    input_source = importlib.import_module("axm_smelt.core.input_source")
    stdin = NonInteractiveStream("alpha beta")

    result = input_source.read_source(input_path=None, stdin=stdin)

    assert result == "alpha beta"


def test_read_source_does_not_consume_interactive_stdin(
    mocker: MockerFixture,
) -> None:
    """AC5: un flux interactif retourne None sans que read soit appelé."""
    input_source = importlib.import_module("axm_smelt.core.input_source")
    stdin = mocker.Mock(spec=["isatty", "read"])
    stdin.isatty.return_value = True

    result = input_source.read_source(input_path=None, stdin=stdin)

    assert result is None
    stdin.read.assert_not_called()
