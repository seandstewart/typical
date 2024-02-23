from __future__ import annotations

import abc
from types import MappingProxyType
from typing import Callable, Dict, Type, TypeVar

from typical import constraints
from typical.compat import Generic

__all__ = ("AbstractSchemaBuilder", "CT", "DefinitionT", "PackageT")


CT = TypeVar("CT", bound=constraints.AbstractConstraints)
DefinitionT = TypeVar("DefinitionT")
PackageT = TypeVar("PackageT")


_SchemaBuilderT = Callable[[CT], DefinitionT]
_SchemaBuilderMapT = Dict[Type[CT], _SchemaBuilderT]


class AbstractSchemaBuilder(abc.ABC, Generic[DefinitionT, PackageT]):
    """The base interface for building schemas from typical's Constraint syntax."""

    def __init__(self):
        self._cache = {}
        self._attached = set()
        self._visited = set()
        self._CONSTRAINT_TO_HANDLER = {
            constraints.StructuredObjectConstraints: self._from_structured_object_constraint,
            constraints.MappingConstraints: self._from_mapping_constraint,
            constraints.ArrayConstraints: self._from_array_constraint,
            constraints.TextConstraints: self._from_text_constraint,
            constraints.DecimalConstraints: self._from_decimal_constraint,
            constraints.NumberConstraints: self._from_number_constraint,
            constraints.MultiConstraints: self._from_multi_constraint,
            constraints.EnumerationConstraints: self._from_enumeration_constraint,
            constraints.TypeConstraints: self._from_type_constraint,
            constraints.UndeclaredTypeConstraints: self._from_undeclared_constraint,
        }

    def build(self, c: CT, *, field_name: str = None) -> DefinitionT:
        if isinstance(c, constraints.DelayedConstraintsProxy):
            c = c.resolved

        if c in self._cache:
            return self._cache[c]

        ctype = c.__class__
        if ctype not in self._CONSTRAINT_TO_HANDLER:
            raise TypeError(f"Unrecognized constraint type: {ctype.__qualname__}.")

        if c in self._visited:
            definition = self._handle_cyclic_constraint(c=c)

        else:
            self._visited.add(c)
            handler = self._CONSTRAINT_TO_HANDLER[ctype]
            definition = handler(c)
            self._visited.remove(c)

        if c.nullable:
            definition = self._wrap_nullable(definition=definition)
        if c.readonly:
            definition = self._handle_readonly(definition=definition)
        if c.writeonly:
            definition = self._handle_writeonly(definition=definition)

        self._cache[c] = definition
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
        self,
        cv: constraints.StructuredObjectConstraints,
        *,
        field_name: str = None,
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_mapping_constraint(
        self,
        c: constraints.MappingConstraints,
        *,
        field_name: str = None,
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_array_constraint(
        self, c: constraints.ArrayConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_text_constraint(
        self, c: constraints.TextConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_decimal_constraint(
        self, c: constraints.DecimalConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_number_constraint(
        self, c: constraints.NumberConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_enumeration_constraint(
        self,
        c: constraints.EnumerationConstraints,
        *,
        field_name: str = None,
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_type_constraint(
        self, c: constraints.TypeConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_multi_constraint(
        self, c: constraints.MultiConstraints, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _from_undeclared_constraint(
        self,
        c: constraints.UndeclaredTypeConstraints,
        *,
        field_name: str = None,
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _handle_cyclic_constraint(
        self, c: CT, *, field_name: str = None
    ) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _gather_definitions(self) -> PackageT:
        ...

    @abc.abstractmethod
    def _wrap_nullable(self, definition: DefinitionT) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _handle_readonly(self, definition: DefinitionT) -> DefinitionT:
        ...

    @abc.abstractmethod
    def _handle_writeonly(self, definition: DefinitionT) -> DefinitionT:
        ...

    _CONSTRAINT_TO_HANDLER: _SchemaBuilderMapT
    _cache: dict[constraints.AbstractConstraints, DefinitionT]
    _attached: set[constraints.AbstractConstraints]
    _visited: set[constraints.AbstractConstraints]
