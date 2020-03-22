#!/usr/bin/env python
import dataclasses
import datetime
import decimal
import enum
import ipaddress
import pathlib
import re
import uuid
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
    Text,
    Tuple,
    MutableMapping,
)

import inflection  # type: ignore
import pendulum

from typic.compat import Final, TypedDict
from typic.generics import ReadOnly, WriteOnly
from typic.serde.obj import SerdeProtocol, Annotation
from typic.serde.resolver import resolver
from typic.types import networking, secret, path
from typic.types.frozendict import FrozenDict
from typic.util import get_args, origin
from .obj import (  # type: ignore
    MultiSchemaField,
    ObjectSchemaField,
    UndeclaredSchemaField,
    Ref,
    SchemaFieldT,
    SchemaType,
    ArraySchemaField,
    BooleanSchemaField,
    IntSchemaField,
    NumberSchemaField,
    StrSchemaField,
    StringFormat,
    NullSchemaField,
)

_IGNORE_DOCS = frozenset({Mapping.__doc__, Generic.__doc__, List.__doc__})

__all__ = ("SchemaBuilder", "SchemaDefinitions", "builder", "get_field_type")

TYPE_TO_FIELD: Mapping[SchemaType, Type[SchemaFieldT]] = {
    SchemaType.ARR: ArraySchemaField,
    SchemaType.BOOL: BooleanSchemaField,
    SchemaType.INT: IntSchemaField,
    SchemaType.NUM: NumberSchemaField,
    SchemaType.OBJ: ObjectSchemaField,
    SchemaType.STR: StrSchemaField,
}


def get_field_type(type: Optional[Union[SchemaType, Any]]) -> Type[SchemaFieldT]:
    if type is None:
        return MultiSchemaField
    if type is NotImplemented:
        return UndeclaredSchemaField
    return TYPE_TO_FIELD[type]


SCHEMA_FIELD_FORMATS: Mapping[type, SchemaFieldT] = FrozenDict(
    {
        str: StrSchemaField(),
        AnyStr: StrSchemaField(),
        Text: StrSchemaField(),
        bytes: StrSchemaField(),
        int: IntSchemaField(),
        bool: BooleanSchemaField(),
        float: NumberSchemaField(),
        list: ArraySchemaField(),
        set: ArraySchemaField(uniqueItems=True),
        tuple: ArraySchemaField(additionalItems=False),
        frozenset: ArraySchemaField(uniqueItems=True, additionalItems=False),
        dict: ObjectSchemaField(),
        object: UndeclaredSchemaField(),
        FrozenDict: ObjectSchemaField(),
        decimal.Decimal: NumberSchemaField(),
        datetime.datetime: StrSchemaField(format=StringFormat.DTIME),
        pendulum.DateTime: StrSchemaField(format=StringFormat.DTIME),
        datetime.date: StrSchemaField(format=StringFormat.DATE),
        pendulum.Date: StrSchemaField(format=StringFormat.DATE),
        datetime.time: StrSchemaField(format=StringFormat.TIME),
        networking.URL: StrSchemaField(format=StringFormat.URI),
        networking.AbsoluteURL: StrSchemaField(format=StringFormat.URI),
        networking.RelativeURL: StrSchemaField(format=StringFormat.URI),
        networking.DSN: StrSchemaField(format=StringFormat.URI),
        pathlib.Path: StrSchemaField(format=StringFormat.URI),
        path.FilePath: StrSchemaField(format=StringFormat.URI),
        path.DirectoryPath: StrSchemaField(format=StringFormat.URI),
        path.PathType: StrSchemaField(format=StringFormat.URI),
        networking.HostName: StrSchemaField(format=StringFormat.HNAME),
        networking.Email: StrSchemaField(format=StringFormat.EMAIL),
        secret.SecretStr: StrSchemaField(),
        secret.SecretBytes: StrSchemaField(),
        uuid.UUID: StrSchemaField(format=StringFormat.UUID),
        re.Pattern: StrSchemaField(format=StringFormat.RE),  # type: ignore
        ipaddress.IPv4Address: StrSchemaField(format=StringFormat.IPV4),
        ipaddress.IPv6Address: StrSchemaField(format=StringFormat.IPV6),
        type(None): NullSchemaField(),
    }
)


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
        self, anno: Annotation, constraints: dict, fields: dict, *, name: str = None
    ):
        args = anno.args
        fields["title"] = self.defname(anno.resolved, name=name)
        doc = getattr(anno.resolved, "__doc__", None)
        if doc not in _IGNORE_DOCS:
            fields["description"] = doc
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
        fields["additionalProperties"] = field

    def _handle_array(self, anno: Annotation, constraints: dict, fields: dict):
        args = anno.args
        has_ellipsis = args[-1] is Ellipsis if args else False
        if has_ellipsis:
            args = args[:-1]
        items: Optional["SchemaFieldT"] = None
        if "items" in constraints:
            citems = constraints["items"]
            multi_keys: Set[str] = {"oneOf", "anyOf", "allOf"} & citems.keys()
            if multi_keys:
                items_fields: MutableMapping[str, Optional[Tuple]] = dict.fromkeys(
                    multi_keys
                )
                k: str
                for k in items_fields:
                    items_fields[k] = (
                        *(get_field_type(x.pop("type"))(**x) for x in citems[k]),
                    )
                items = MultiSchemaField(**items_fields)
            else:
                items = get_field_type(citems.pop("type"))(**citems)
        if args:
            constrs = {*(self.get_field(resolver.resolve(x)) for x in args)}
            if items:
                constrs.add(items)
            fields["items"] = (*constrs,) if len(constrs) > 1 else constrs.pop()
            if anno.origin in {tuple, frozenset}:
                fields["additionalItems"] = False if not has_ellipsis else None
            if anno.origin in {set, frozenset}:
                fields["uniqueItems"] = True
        elif items:
            fields["items"] = items

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
        # Get known schemas mapped to Python types.
        formats = SCHEMA_FIELD_FORMATS
        # `use` is the based annotation we will use for building the schema
        use = getattr(anno.origin, "__parent__", anno.origin)
        # If there's not a static annotation, short-circuit the rest of the checks.
        schema: SchemaFieldT
        if use in {Any, anno.EMPTY}:
            schema = UndeclaredSchemaField()
            self.__cache[anno] = schema
            return schema

        # Unions are `oneOf`, get a new field for each arg and return.
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
        if use in formats:
            constraints: dict = (
                protocol.constraints.for_schema() if protocol.constraints else {}
            )
            fields: dict = {
                "enum": enum_,
                "default": default,
                "readOnly": ro,
                "writeOnly": wo,
            }
            # `use` should always be a dict if the annotation is a Mapping,
            # thanks to `origin()` & `resolve()`.
            if use is dict:
                self._handle_mapping(anno, constraints, fields, name=name)
            elif use in {tuple, set, frozenset, list}:
                self._handle_array(anno, constraints, fields)
            fields.update(
                {x: constraints[x] for x in constraints.keys() - fields.keys()}
            )
            base: SchemaFieldT = formats[use]
            schema = dataclasses.replace(base, **fields)
        else:
            schema = self.build_schema(use, name=self.defname(use, name=name))

        self.__cache[anno] = schema
        return schema

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
            if isinstance(field, ObjectSchemaField):
                definitions.update(**(field.definitions or {}))  # type: ignore
                field = dataclasses.replace(field, definitions=None)
                definitions[field.title] = field  # type: ignore
                properties[nm] = Ref(f"#/definitions/{field.title}")
            # Otherwise just add as a property with the attr name
            else:
                properties[nm] = field
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
                x: y.primitive() if isinstance(y, ObjectSchemaField) else y
                for x, y in definitions["definitions"].items()
            }
        return definitions


builder = SchemaBuilder()
