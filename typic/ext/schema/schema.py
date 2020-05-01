#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import enum
from typing import (
    Union,
    Type,
    Mapping,
    Optional,
    Dict,
    Any,
    List,
    Generic,
    cast,
    Set,
    AnyStr,
)

import inflection  # type: ignore

from typic.common import ReadOnly, WriteOnly
from typic.serde.resolver import resolver
from typic.serde.common import SerdeProtocol, Annotation
from typic.compat import Final, TypedDict
from typic.util import get_args, origin
from typic.checks import istypeddict, isnamedtuple
from typic.types.frozendict import FrozenDict

from .field import (  # type: ignore
    MultiSchemaField,
    ObjectSchemaField,
    UndeclaredSchemaField,
    Ref,
    SchemaFieldT,
    SCHEMA_FIELD_FORMATS,
    get_field_type,
    SchemaType,
    ArraySchemaField,
)

_IGNORE_DOCS = frozenset({Mapping.__doc__, Generic.__doc__, List.__doc__})

__all__ = ("SchemaBuilder", "SchemaDefinitions", "builder")


_KNOWN = (*(f for f in SCHEMA_FIELD_FORMATS.keys() if f not in {AnyStr, object}),)


class SchemaDefinitions(TypedDict):
    """A :py:class:`TypedDict` for JSON Schema Definitions."""

    definitions: Dict[str, Union[ObjectSchemaField, Mapping]]


class SchemaBuilder:
    """Build a JSON schema from an object.

    Notes
    -----
    This shouldn't be used directly.
    Schema generation is handled automatically when a class is wrapped.

    See Also
    --------
    :py:func:`~typic.typed.glob.wrap_cls`
    :py:func:`~typic.klass.klass`
    """

    def __init__(self):
        self.__cache = {}

    def _handle_mapping(self, anno: Annotation, constraints: dict, *, name: str = None):
        args = anno.args
        constraints["title"] = self.defname(anno.resolved, name=name)
        doc = getattr(anno.resolved, "__doc__", None)
        if doc not in _IGNORE_DOCS:
            constraints["description"] = doc
        field: Optional[SchemaFieldT] = None
        if args:
            field = self.get_field(resolver.resolve(args[-1]))
        if "additionalProperties" in constraints:
            other = constraints["additionalProperties"]
            # this is coming in from a constraint
            if isinstance(other, dict):
                schema_type = other.pop("type", None)
                field = field or get_field_type(schema_type)()
                if isinstance(field, MultiSchemaField):
                    for k in {"oneOf", "anyOf", "allOf"} & other.keys():
                        other[k] = tuple(
                            get_field_type(x.pop("type"))(**x) for x in other[k]
                        )
                field = dataclasses.replace(field, **other)
        constraints["additionalProperties"] = field

    def _handle_array(self, anno: Annotation, constraints: dict):
        args = anno.args
        has_ellipsis = args[-1] is Ellipsis if args else False
        if has_ellipsis:
            args = args[:-1]
        if args:
            constrs = set(self.get_field(resolver.resolve(x)) for x in args)
            constraints["items"] = (*constrs,) if len(constrs) > 1 else constrs.pop()
            if anno.origin in {tuple, frozenset}:
                constraints["additionalItems"] = False if not has_ellipsis else None
            if anno.origin in {set, frozenset}:
                constraints["uniqueItems"] = True
        elif "items" in constraints:
            items: dict = constraints["items"]
            multi_keys: Set[str] = {"oneOf", "anyOf", "allOf"} & items.keys()
            if multi_keys:
                for k in multi_keys:
                    items[k] = tuple(
                        get_field_type(x.pop("type"))(**x) for x in items[k]
                    )
                    constraints["items"] = MultiSchemaField(**items)
            else:
                constraints["items"] = get_field_type(items.pop("type"))(**items)

    def get_field(
        self,
        protocol: SerdeProtocol,
        *,
        ro: bool = None,
        wo: bool = None,
        name: str = None,
    ) -> "SchemaFieldT":
        """Get a field definition for a JSON Schema."""
        anno = protocol.annotation
        if anno in self.__cache:
            return self.__cache[anno]
        # Get the default value
        # `None` gets filtered out down the line. this is okay.
        # If a field isn't required an empty default is functionally the same
        # as a default to None for the JSON schema.
        default = anno.parameter.default if anno.has_default else None
        # `use` is the based annotation we will use for building the schema
        use = getattr(anno.origin, "__parent__", anno.origin)
        # If there's not a static annotation, short-circuit the rest of the checks.
        schema: SchemaFieldT
        if use in {Any, anno.EMPTY}:
            schema = UndeclaredSchemaField()
            self.__cache[anno] = schema
            return schema

        # Unions are `anyOf`, get a new field for each arg and return.
        # {'type': ['string', 'integer']} ==
        #   {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
        # We don't care about syntactic sugar if it's functionally the same.
        if use is Union:
            schema = MultiSchemaField(
                title=self.defname(anno.resolved, name=name) if name else None,
                anyOf=tuple(
                    self.get_field(resolver.resolve(x))
                    for x in get_args(anno.un_resolved)
                ),
            )
            self.__cache[anno] = schema
            return schema

        # Check if this should be ro/wo
        if use in {ReadOnly, WriteOnly, Final}:
            ro = (use in {ReadOnly, Final}) or None
            wo = (use is WriteOnly) or None
            use = origin(anno.resolved)
            use = getattr(use, "__parent__", use)

        # Check for an enumeration
        enum_ = None
        if issubclass(use, enum.Enum):
            use = cast(Type[enum.Enum], use)
            enum_ = tuple(x.value for x in use)
            use = getattr(use._member_type_, "__parent__", use._member_type_)  # type: ignore

        # If this is ro with a default, we can consider this a const
        # Which is an enum with a single value -
        # we don't currently honor `{'const': <val>}` since it's just syntactic sugar.
        if ro and default:
            enum_ = (default.value if isinstance(default, enum.Enum) else default,)
            ro = None

        # If we've got a base object, use it
        base: Optional[SchemaFieldT]
        if use is object:
            base = UndeclaredSchemaField()
        elif istypeddict(use) or isnamedtuple(use):
            base = None
        else:
            base = cast(SchemaFieldT, SCHEMA_FIELD_FORMATS.get_by_parent(use))
        if base:
            constraints = (
                protocol.constraints.for_schema() if protocol.constraints else {}
            )
            constraints.update(enum=enum_, default=default, readOnly=ro, writeOnly=wo)
            # `use` should always be a dict if the annotation is a Mapping,
            # thanks to `origin()` & `resolve()`.
            if isinstance(base, ObjectSchemaField):
                self._handle_mapping(anno, constraints, name=name)
            elif isinstance(base, ArraySchemaField):
                self._handle_array(anno, constraints)
            schema = dataclasses.replace(base, **constraints)
        else:
            try:
                schema = self.build_schema(use, name=self.defname(use, name=name))
            except (ValueError, TypeError):
                schema = UndeclaredSchemaField(
                    enum=enum_,
                    title=self.defname(use, name=name),
                    default=default,
                    readOnly=ro,
                    writeOnly=wo,
                )

        self.__cache[anno] = schema
        return schema

    @staticmethod
    def _flatten_object_definitions(
        definitions: Dict[str, Any], field: ObjectSchemaField
    ):
        definitions.update(**(field.definitions or {}))  # type: ignore
        field = dataclasses.replace(field, definitions=None)
        definitions[field.title] = field  # type: ignore
        return Ref(f"#/definitions/{field.title}")

    def _flatten_array_definitions(
        self, definitions: Dict[str, Any], field: ArraySchemaField
    ):
        replace = {}
        for field_name in ("items", "contains", "additionalItems"):
            it = getattr(field, field_name)
            if isinstance(it, ObjectSchemaField):
                ref = self._flatten_object_definitions(definitions, it)
                replace[field_name] = ref
        return dataclasses.replace(field, **replace) if replace else field

    def _flatten_multi_definitions(
        self, definitions: Dict[str, Any], field: MultiSchemaField
    ) -> MultiSchemaField:
        replace = {}
        for field_name in ("anyOf", "allOf", "oneOf"):
            it = getattr(field, field_name)
            if it:
                flattened = []
                for f in it:
                    nf = self._flatten_definitions(definitions, f)
                    flattened.append(nf)
                replace[field_name] = (*flattened,)
        return dataclasses.replace(field, **replace) if replace else field

    def _flatten_definitions(self, definitions: Dict[str, Any], field: SchemaFieldT):
        if isinstance(field, ObjectSchemaField):
            return self._flatten_object_definitions(definitions, field)
        elif isinstance(field, ArraySchemaField):
            return self._flatten_array_definitions(definitions, field)
        elif isinstance(field, MultiSchemaField):
            return self._flatten_multi_definitions(definitions, field)
        return field

    @staticmethod
    def defname(obj, name: str = None) -> Optional[str]:
        """Get the definition name for an object."""
        defname = name or getattr(obj, "__name__", None)
        if (obj is dict or origin(obj) is dict) and name:
            defname = name
        return inflection.camelize(defname) if defname else None

    def build_schema(self, obj: Type, *, name: str = None) -> "ObjectSchemaField":
        """Build a valid JSON Schema, including nested schemas."""
        if obj in self.__cache:  # pragma: nocover
            return self.__cache[obj]

        protocols: Dict[str, SerdeProtocol] = resolver.protocols(obj)
        definitions: Dict[str, Any] = {}
        properties: Dict[str, Any] = {}
        required: List[str] = []
        total: bool = getattr(obj, "__total__", True)
        for nm, protocol in protocols.items():
            field = self.get_field(protocol, name=nm)
            # If we received an object schema,
            # figure out a name and inherit the definitions.
            flattened = self._flatten_definitions(definitions, field)
            properties[nm] = flattened
            # Check for required field(s)
            if not protocol.annotation.has_default:
                required.append(nm)
        schema = ObjectSchemaField(
            title=name or self.defname(obj),
            description=obj.__doc__,
            properties=FrozenDict(properties),
            additionalProperties=False,
            required=(*required,) if total else (),
            definitions=FrozenDict(definitions),
        )
        self.__cache[obj] = schema
        return schema

    def all(self, primitive: bool = False) -> SchemaDefinitions:
        """Get all of the JSON Schema objects which have been defined.

        `typical` maintains a register of all resolved schema definitions.
        This method give high-level, immediate read access to that registry.

        Parameters
        ----------
        primitive

        Examples
        --------
        >>> import json
        >>> import typic
        >>> schemas = typic.schemas(primitive=True)
        >>> print(json.dumps(schemas["definitions"]["Duck"], indent=2))
        {
          "type": "object",
          "title": "Duck",
          "description": "Duck(color: str)",
          "properties": {
            "color": {
              "type": "string"
            }
          },
          "additionalProperties": false,
          "required": [
            "color"
          ]
        }
        """
        definitions = SchemaDefinitions(definitions={})
        schm: ObjectSchemaField
        for obj, schm in self.__cache.items():
            if schm.type != SchemaType.OBJ:
                continue
            definitions["definitions"].update(
                {
                    x: dataclasses.replace(y, definitions=None)
                    for x, y in (schm.definitions or {}).items()
                }
            )
            definitions["definitions"][
                schm.title  # type: ignore
            ] = dataclasses.replace(schm, definitions=None)
        if primitive:
            definitions["definitions"] = {
                x: y.primitive() if isinstance(y, ObjectSchemaField) else y
                for x, y in definitions["definitions"].items()
            }
        return definitions


builder = SchemaBuilder()
