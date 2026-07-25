"""Real ABC -> concrete-override fixture for abstract-following AST tests.

Parsed by tree-sitter (no mocks): a single ``@abstractmethod`` declared on an
``ABC`` base plus exactly one concrete subclass overriding it, so the on-disk
AST carries a genuine abstract -> concrete pair. Consumed by
``tests/integration/test_ast_context__ast_inspect.py`` to exercise the
abstract-method-following path of ``ToolAstContext`` / ``ast_inspect``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractProcessor(ABC):
    """Abstract base declaring the ``process`` contract."""

    @abstractmethod
    def process(self, payload: str) -> str:
        """Transform *payload* -- abstract, deferred to subclasses."""
        ...


class ConcreteProcessor(AbstractProcessor):
    """Concrete implementation overriding the abstract contract."""

    def process(self, payload: str) -> str:
        """Return the upper-cased *payload* -- the concrete override."""
        return payload.upper()
