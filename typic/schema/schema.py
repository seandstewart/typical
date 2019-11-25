#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import enum
from typing import Union, Type, Mapping, Optional, Dict, Any, List, Generic, cast

import inflection  # type: ignore

from typic import api
from typic.compat import Final, TypedDict
from typic.util import get_args, origin
from typic.types.frozendict import FrozenDict

from .field import (  # type: ignore
    MultiSchemaField,
    ObjectSchemaField,
    UndeclaredSchemaField,
    ReadOnly,
    Ref,
    SchemaField,
    WriteOnly,
    SCHEMA_FIELD_FORMATS,
    get_field_type,
    SchemaType,
)

_IGNORE_DOCS = frozenset({Mapping.__doc__, Generic.__doc__, List.__doc__})

__all__ = ("SchemaBuilder", "SchemaDefinitions")


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

    def _handle_mapping(
        self, anno: "api.ResolvedAnnotation", constraints: dict, *, name: str = None
    ):
        args = get_args(anno.annotation)
        constraints["title"] = self.defname(anno.annotation, name=name)
        doc = getattr(anno.annotation, "__doc__", None)
        if doc not in _IGNORE_DOCS:
            constraints["description"] = doc
        field: Optional[SchemaField] = None
        if args:
            field = self.get_field(api.coerce.resolve(args[-1]))
        if "additionalProperties" in constraints:
            other = constraints["additionalProperties"]
            # this is coming in from a constraint
            if isinstance(other, dict):
                schema_type = other.pop("type", None)
                # We assume here the user did the right thing and declared
                # A constraint type that matches the subscripted type
                if field:
                    field = dataclasses.replace(field, **other)
                else:
                    field = get_field_type(schema_type)(**other)
        constraints["additionalProperties"] = field

    def _handle_array(self, anno: "api.ResolvedAnnotation", constraints: dict):
        args = get_args(anno.annotation)
        has_ellipsis = args[-1] is Ellipsis if args else False
        if has_ellipsis:
            args = args[:-1]
        if "items" in constraints:
            constraints["items"] = (
                tuple(get_field_type(x.pop("type"))(**x) for x in constraints["items"])
                if isinstance(constraints["items"], list)
                else get_field_type(constraints["items"].pop("type"))(
                    **constraints["items"]
                )
            )
        if args:
            constrs = set(self.get_field(api.coerce.resolve(x)) for x in args)
            constraints["items"] = tuple({*constraints.get("items", ())} | constrs)
            if anno.origin in {tuple, frozenset}:
                constraints["additionalItems"] = False if not has_ellipsis else None
            if anno.origin in {set, frozenset}:
                constraints["uniqueItems"] = True

    def get_field(
        self,
        anno: "api.ResolvedAnnotation",
        *,
        ro: bool = None,
        wo: bool = None,
        name: str = None,
    ) -> "SchemaField":
        """Get a field definition for a JSON Schema."""
        if anno in self.__cache:
            return self.__cache[anno]
        # Get the default value
        # `None` gets filtered out down the line. this is okay.
        # If a field isn't required an empty default is functionally the same
        # as a default to None for the JSON schema.
        default = (
            None if anno.parameter.default is anno.EMPTY else anno.parameter.default
        )
        # Get known schemas mapped to Python types.
        formats = SCHEMA_FIELD_FORMATS
        # `use` is the based annotation we will use for building the schema
        use = anno.origin
        # If there's not a static annotation, short-circuit the rest of the checks.
        schema: SchemaField
        if use is anno.EMPTY:
            schema = UndeclaredSchemaField()
            self.__cache[anno] = schema
            return schema

        # Unions are `oneOf`, get a new field for each arg and return.
        # {'type': ['string', 'integer']} ==
        #   {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
        # We don't care about syntactic sugar if it's functionally the same.
        if use is Union:
            schema = MultiSchemaField(
                title=self.defname(anno.annotation, name=name) if name else None,
                oneOf=tuple(
                    self.get_field(api.coerce.resolve(x))
                    for x in get_args(anno.un_resolved)
                ),
            )
            self.__cache[anno] = schema
            return schema

        # Check if this should be ro/wo
        if use in {ReadOnly, WriteOnly, Final}:
            ro = (use in {ReadOnly, Final}) or None
            wo = (use is WriteOnly) or None
            use = origin(anno.un_resolved)

        # Check for an enumeration
        enum_ = None
        if issubclass(use, enum.Enum):
            use = cast(Type[enum.Enum], use)
            enum_ = tuple(x.value for x in use)
            use = use._member_type_  # type: ignore

        # If this is ro with a default, we can consider this a const
        # Which is an enum with a single value -
        # we don't currently honor `{'const': <val>}` since it's just syntactic sugar.
        if ro and default:
            enum_ = (default.value if isinstance(default, enum.Enum) else default,)
            ro = None

        # If we've got a base object, use it
        if use in formats:
            constraints = anno.constraints.for_schema() if anno.constraints else {}
            constraints.update(enum=enum_, default=default, readOnly=ro, writeOnly=wo)
            # `use` should always be a dict if the annotation is a Mapping,
            # thanks to `origin()` & `resolve()`.
            if use is dict:
                self._handle_mapping(anno, constraints, name=name)
            elif use in {tuple, set, frozenset, list}:
                self._handle_array(anno, constraints)
            base: SchemaField = formats[use]
            schema = dataclasses.replace(base, **constraints)
            self.__cache[anno] = schema
            return schema

        # Else assume this is a custom object and build a new schema for it
        return self.build_schema(use, name=self.defname(use, name=name))

    @staticmethod
    def defname(obj, name: str = None) -> Optional[str]:
        """Get the definition name for an object."""
        defname = getattr(obj, "__name__", None) or name
        if (obj is dict or origin(obj) is dict) and name:
            defname = name
        return inflection.camelize(defname) if defname else None

    def build_schema(self, obj: Type, *, name: str = None) -> "ObjectSchemaField":
        """Build a valid JSON Schema, including nested schemas."""
        if obj in self.__cache:
            return self.__cache[obj]

        annotations: Dict[str, api.ResolvedAnnotation] = api.annotations(obj)
        definitions: Dict[str, Any] = {}
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for nm, annotation in annotations.items():
            field = self.get_field(annotation, name=nm)
            # If we received an object schema, figure out a name and inherit the definitions.
            if isinstance(field, ObjectSchemaField):
                definitions.update(**(field.definitions or {}))  # type: ignore
                field = dataclasses.replace(field, definitions=None)
                definitions[field.title] = field  # type: ignore
                properties[nm] = Ref(f"#/definitions/{field.title}")
            # Otherwise just add as a property with the attr name
            else:
                properties[nm] = field
            # Check for required field(s)
            if annotation.parameter.default is annotation.EMPTY:
                required.append(nm)
        schema = ObjectSchemaField(
            title=name or self.defname(obj),
            description=obj.__doc__,
            properties=FrozenDict(properties),
            additionalProperties=False,
            required=tuple(required),
            definitions=FrozenDict(definitions),
        )
        self.__cache[obj] = schema
        return schema

    def all(self, primitive: bool = False) -> SchemaDefinitions:
        """Get all of the JSON Schema objects which have been defined.

        ``typical`` maintains a register of all resolved schema definitions.
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
                x: y.asdict() if isinstance(y, ObjectSchemaField) else y
                for x, y in definitions["definitions"].items()
            }
        return definitions
