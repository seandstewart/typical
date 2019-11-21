#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import copy
import dataclasses
import datetime
import decimal
import enum
import ipaddress
import pathlib
import re
import uuid
from typing import (
    ClassVar,
    Collection,
    List,
    Mapping,
    Any,
    Union,
    Callable,
    Tuple,
    Type,
    Pattern,
    Generic,
    TypeVar,
    AnyStr,
    Optional,
    Dict,
    Text,
)

from typic.checks import isbuiltintype
from typic.util import filtered_repr, cached_property, origin, primitive
from typic.types import dsn, email, frozendict, path, secret, url
from .compat import fastjsonschema

__all__ = (
    "ArraySchemaField",
    "BaseSchemaField",
    "BooleanSchemaField",
    "IntSchemaField",
    "NumberSchemaField",
    "MultiSchemaField",
    "ObjectSchemaField",
    "ReadOnly",
    "Ref",
    "SchemaField",
    "SchemaType",
    "StringFormat",
    "StrSchemaField",
    "UndeclaredSchemaField",
    "WriteOnly",
)

T = TypeVar("T")


class ReadOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be read-only."""

    pass


class WriteOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be write-only."""

    pass


class SchemaType(str, enum.Enum):
    """The official primitive types supported by JSON Schema.

    See Also
    --------
    `JSON Schema Types <https://json-schema.org/understanding-json-schema/reference/type.html>`_
    """

    STR = "string"
    INT = "integer"
    NUM = "number"
    OBJ = "object"
    ARR = "array"
    BOOL = "boolean"


@dataclasses.dataclass(frozen=True)
class Ref:
    """A JSON Schema ref (pointer).

    Usually for directing a validator to another schema definition.
    """

    ref: str

    def asdict(self) -> dict:  # pragma: nocover
        return {"$ref": self.ref}

    primitive = primitive


class StringFormat(str, enum.Enum):
    """The official string 'formats' supported by JSON Schema.

    See Also
    --------
    `JSON Schema Strings <https://json-schema.org/understanding-json-schema/reference/string.html>`_
    """

    TIME = "time"
    DATE = "date"
    DTIME = "date-time"
    HNAME = "hostname"
    URI = "uri"
    EMAIL = "email"
    UUID = "uuid"
    RE = "regex"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


def schema_asdict(obj: "BaseSchemaField") -> dict:
    """Recursively output a SchemaField object as a dict."""
    formats = SCHEMA_FIELD_FORMATS
    if isinstance(obj, Ref):
        return obj.asdict()
    if isinstance(obj, BaseSchemaField):
        final: Dict[str, Any] = {}
        if obj.type is not NotImplemented:
            final = {"type": obj.type.value}

        f: dataclasses.Field
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            if val is None:
                continue
            if isinstance(val, (BaseSchemaField, Ref)):
                val = val.asdict()
            elif isinstance(val, Mapping):
                val = {x: schema_asdict(y) for x, y in val.items()}
            elif isinstance(val, Collection) and not isinstance(val, (str, bytes)):
                val = [schema_asdict(x) for x in val]
            else:
                val = dataclasses._asdict_inner(val, dict_factory=dict)  # type: ignore
            final[f.name] = val
    elif origin(obj) in formats:
        final = formats[origin(obj)]
    else:
        final = obj if isbuiltintype(type(obj)) else ObjectSchemaField().asdict()
    return final


@dataclasses.dataclass(frozen=True, repr=False)
class BaseSchemaField:
    """The base JSON Schema Field."""

    type: ClassVar[SchemaType] = NotImplemented
    format: Optional[str] = None
    enum: Optional[Tuple[Any, ...]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    default: Optional[str] = None
    examples: Optional[List[Any]] = None
    readOnly: Optional[bool] = None
    writeOnly: Optional[bool] = None
    extensions: Optional[Tuple[frozendict.FrozenDict[str, Any], ...]] = None

    asdict = schema_asdict
    primitive = primitive

    __repr = cached_property(filtered_repr)

    def __repr__(self) -> str:  # pragma: nocover
        return self.__repr

    @cached_property
    def validator(self) -> Callable:  # pragma: nocover
        """The JSON Schema validator.

        Notes
        -----
        If ``fastjsonschema`` is not installed, this will raise a ValueError.

        See Also
        --------
        `fastjsonschema <https://horejsek.github.io/python-fastjsonschema/>`_
        """
        if fastjsonschema:
            return fastjsonschema.compile(self.asdict())
        raise ValueError("Can't compile validator, 'fastjsonschema' is not installed.")

    def validate(self, obj) -> Any:  # pragma: nocover
        """Validate an object against the defined JSON Schema."""
        return self.validator(obj)

    def copy(self):  # pragma: nocover
        """Return a new copy of this schema field."""
        return copy.deepcopy(self)


@dataclasses.dataclass(frozen=True, repr=False)
class UndeclaredSchemaField(BaseSchemaField):
    """A sentinel object for generating an empty schema."""

    pass


@dataclasses.dataclass(frozen=True, repr=False)
class MultiSchemaField(BaseSchemaField):
    """A schema field which supports multiple types."""

    anyOf: Optional[Tuple["SchemaField", ...]] = None
    allOf: Optional[Tuple["SchemaField", ...]] = None
    oneOf: Optional[Tuple["SchemaField", ...]] = None


@dataclasses.dataclass(frozen=True, repr=False)
class StrSchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``string`` type.

    See Also
    --------
    `JSON Schema String Type <https://json-schema.org/understanding-json-schema/reference/string.html>`_
    `JSON Schema RegEx <https://json-schema.org/understanding-json-schema/reference/regular_expressions.html>`_
    """

    type = SchemaType.STR
    pattern: Optional[Pattern] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None


Number = Union[int, float, decimal.Decimal]


@dataclasses.dataclass(frozen=True, repr=False)
class IntSchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``integer`` type.

    See Also
    --------
    `JSON Schema Numeric Types <https://json-schema.org/understanding-json-schema/reference/numeric.html>`_
    """

    type = SchemaType.INT
    multipleOf: Optional[Number] = None
    maximum: Optional[Number] = None
    minimum: Optional[Number] = None
    exclusiveMaximum: Optional[Number] = None
    exclusiveMinimum: Optional[Number] = None


@dataclasses.dataclass(frozen=True, repr=False)
class NumberSchemaField(IntSchemaField):
    """A JSON Schema Field for the ``number`` type.

    See Also
    --------
    `JSON Schema Numeric Types <https://json-schema.org/understanding-json-schema/reference/numeric.html>`_
    """

    type = SchemaType.NUM


@dataclasses.dataclass(frozen=True, repr=False)
class BooleanSchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``boolean`` type.

    See Also
    --------
    `JSON Schema Boolean Type <https://json-schema.org/understanding-json-schema/reference/boolean.html>`_
    """

    type = SchemaType.BOOL


NestedSchemaField = Union[Collection["SchemaField"], "SchemaField"]


@dataclasses.dataclass(frozen=True, repr=False)
class ObjectSchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``object`` type.

    See Also
    --------
    `JSON Schema Object Type <https://json-schema.org/understanding-json-schema/reference/object.html>`_
    """

    type = SchemaType.OBJ
    properties: Optional[Mapping[str, Union["SchemaField", "Ref"]]] = None
    additionalProperties: Optional[Union[bool, NestedSchemaField]] = None
    maxProperties: Optional[int] = None
    minProperties: Optional[int] = None
    required: Optional[Collection] = None
    propertyNames: Optional[Mapping[str, Pattern]] = None
    patternProperties: Optional[Mapping[Pattern, "SchemaField"]] = None
    dependencies: Optional[Mapping[str, Union[Tuple[str], "ObjectSchemaField"]]] = None
    definitions: Optional[frozendict.FrozenDict[str, "ObjectSchemaField"]] = None


@dataclasses.dataclass(frozen=True, repr=False)
class ArraySchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``array`` type.

    See Also
    --------
    `JSON Schema Array Type <https://json-schema.org/understanding-json-schema/reference/array.html>`_
    """

    type = SchemaType.ARR
    items: Optional[NestedSchemaField] = None
    contains: Optional[NestedSchemaField] = None
    additionalItems: Optional[bool] = None
    minItems: Optional[int] = None
    maxItems: Optional[int] = None
    uniqueItems: Optional[bool] = None


SchemaField = Union[
    StrSchemaField,
    IntSchemaField,
    NumberSchemaField,
    BooleanSchemaField,
    ObjectSchemaField,
    ArraySchemaField,
    MultiSchemaField,
    UndeclaredSchemaField,
]
"""A type-alias for the defined JSON Schema Fields."""


TYPE_TO_FIELD: Mapping[SchemaType, Type[SchemaField]] = {
    SchemaType.ARR: ArraySchemaField,
    SchemaType.BOOL: BooleanSchemaField,
    SchemaType.INT: IntSchemaField,
    SchemaType.NUM: NumberSchemaField,
    SchemaType.OBJ: ObjectSchemaField,
    SchemaType.STR: StrSchemaField,
}


def get_field_type(type: Optional[Union[SchemaType, Any]]) -> Type[SchemaField]:
    if type is None:
        return MultiSchemaField
    if type is NotImplemented:
        return UndeclaredSchemaField
    return TYPE_TO_FIELD[type]


SCHEMA_FIELD_FORMATS: frozendict.FrozenDict[type, SchemaField] = frozendict.FrozenDict(
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
        frozendict.FrozenDict: ObjectSchemaField(),
        decimal.Decimal: NumberSchemaField(),
        datetime.datetime: StrSchemaField(format=StringFormat.DTIME),
        datetime.date: StrSchemaField(format=StringFormat.DATE),
        datetime.time: StrSchemaField(format=StringFormat.TIME),
        url.URL: StrSchemaField(format=StringFormat.URI),
        url.AbsoluteURL: StrSchemaField(format=StringFormat.URI),
        url.RelativeURL: StrSchemaField(format=StringFormat.URI),
        dsn.DSN: StrSchemaField(format=StringFormat.URI),
        pathlib.Path: StrSchemaField(format=StringFormat.URI),
        path.FilePath: StrSchemaField(format=StringFormat.URI),
        path.DirectoryPath: StrSchemaField(format=StringFormat.URI),
        path.PathType: StrSchemaField(format=StringFormat.URI),
        url.HostName: StrSchemaField(format=StringFormat.HNAME),
        email.Email: StrSchemaField(format=StringFormat.EMAIL),
        secret.SecretStr: StrSchemaField(),
        secret.SecretBytes: StrSchemaField(),
        uuid.UUID: StrSchemaField(format=StringFormat.UUID),
        re.Pattern: StrSchemaField(format=StringFormat.RE),  # type: ignore
        ipaddress.IPv4Address: StrSchemaField(format=StringFormat.IPV4),
        ipaddress.IPv6Address: StrSchemaField(format=StringFormat.IPV6),
    }
)
