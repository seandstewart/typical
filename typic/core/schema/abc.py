from __future__ import annotations

import abc
from types import MappingProxyType
from typing import Callable, Dict, Type, TypeVar

from typic.compat import Generic
from typic.core import constraints

__all__ = ("AbstractSchemaBuilder", "CT", "DefinitionT", "PackageT")


CT = TypeVar("CT", bound=constraints.AbstractConstraints)
DefinitionT = TypeVar("DefinitionT")
PackageT = TypeVar("PackageT")


_SchemaBuilderT = Callable[[CT], DefinitionT]
_SchemaBuilderMapT = Dict[Type[CT], _SchemaBuilderT]


class AbstractSchemaBuilder(abc.ABC, Generic[DefinitionT, PackageT]):
    """The base interface for building schemas from typical's Constraint syntax."""

    def __init_subclass__(cls, **kwargs):
        cls._CONSTRAINT_TO_HANDLER = {
            constraints.StructuredObjectConstraints: cls._from_structured_object_constraint,
            constraints.MappingConstraints: cls._from_mapping_constraint,
            constraints.ArrayConstraints: cls._from_array_constraint,
            constraints.TextConstraints: cls._from_text_constraint,
            constraints.DecimalConstraints: cls._from_decimal_constraint,
            constraints.NumberConstraints: cls._from_number_constraint,
            constraints.MultiConstraints: cls._from_multi_constraint,
            constraints.EnumerationConstraints: cls._from_enumeration_constraint,
            constraints.TypeConstraints: cls._from_type_constraint,
            constraints.DelayedConstraintsProxy: cls._from_delayed_constraint,
        }

    def __init__(self):
        self._cache: dict[CT, DefinitionT] = {}
        self._attached: set[CT] = set()
        self._stack: set[CT] = set()

    def build(self, c: CT) -> DefinitionT:
        if c in self._stack:
            return self._handle_cyclic_constraint(c=c)

        if c in self._cache:
            return self._cache[c]

        ctype = c.__class__
        if ctype not in self._CONSTRAINT_TO_HANDLER:
            raise TypeError(f"Unrecognized constraint type: {ctype.__qualname__}.")

        self._stack.add(c)
        handler = self._CONSTRAINT_TO_HANDLER[ctype]
        definition = handler(self, c)  # type: ignore[call-arg]
        if c.nullable:
            definition = self._wrap_nullable(definition=definition)
        self._cache[c] = definition
        self._stack.remove(c)
        return definition

    def attach(self, c: CT):
        self._attached.add(c)

    def all(self) -> PackageT:
        while self._attached:
            c = self._attached.pop()
            self.build(c)
        return self._gather_definitions()

    def forget(self, c: CT):
        if c in self._attached:
            self._attached.remove(c)
        if c in self._cache:
            self._cache.pop(c)

    def cache_clear(self):
        self._attached.clear()
        self._cache.clear()

    def cache_view(self) -> MappingProxyType:
        return MappingProxyType(self._cache)

    @abc.abstractmethod
    def _from_structured_object_constraint(
        self, cv: constraints.StructuredObjectConstraints
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_mapping_constraint(
        self, c: constraints.MappingConstraints
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_array_constraint(self, c: constraints.ArrayConstraints) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_text_constraint(self, c: constraints.TextConstraints) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_decimal_constraint(
        self, c: constraints.DecimalConstraints
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_number_constraint(self, c: constraints.NumberConstraints) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_enumeration_constraint(
        self, c: constraints.EnumerationConstraints
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_type_constraint(self, c: constraints.TypeConstraints) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_multi_constraint(self, c: constraints.MultiConstraints) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_delayed_constraint(
        self, c: constraints.DelayedConstraintsProxy
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _handle_cyclic_constraint(self, c: CT) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _gather_definitions(self) -> PackageT:
        ...

    @abc.abstractmethod
    def _wrap_nullable(self, definition: DefinitionT) -> DefinitionT:
        ...

    _CONSTRAINT_TO_HANDLER: _SchemaBuilderMapT
