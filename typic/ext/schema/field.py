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
    AnyStr,
    Optional,
    Text,
)

import pendulum

from typic.ext.json import dumps
from typic.serde.common import SerdeFlags
from typic.serde.resolver import resolver
from typic.util import filtered_repr, cached_property, TypeMap, ReprT, slotted
from typic.types import dsn, email, frozendict, path, secret, url
from .compat import fastjsonschema

__all__ = (
    "ArraySchemaField",
    "BaseSchemaField",
    "BooleanSchemaField",
    "IntSchemaField",
    "MultiSchemaField",
    "NumberSchemaField",
    "NullSchemaField",
    "ObjectSchemaField",
    "Ref",
    "SchemaFieldT",
    "SchemaType",
    "StringFormat",
    "StrSchemaField",
    "UndeclaredSchemaField",
    "get_field_type",
)


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
    NULL = "null"


class _Serializable:
    __slots__ = ()

    def primitive(self, *, lazy: bool = False, name: ReprT = None) -> Mapping[str, Any]:
        return resolver.primitive(self, lazy=lazy, name=name)

    def tojson(self, *, indent: int = 0, ensure_ascii: bool = False, **kwargs) -> str:
        return dumps(
            self.primitive(lazy=True),
            indent=indent,
            ensure_ascii=ensure_ascii,
            **kwargs,
        )


@slotted
@dataclasses.dataclass(frozen=True)
class Ref(_Serializable):
    """A JSON Schema ref (pointer).

    Usually for directing a validator to another schema definition.
    """

    __serde_flags__ = SerdeFlags(fields={"ref": "$ref"})

    ref: str


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


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class BaseSchemaField(_Serializable):
    """The base JSON Schema Field."""

    __serde_flags__ = SerdeFlags(omit=(None, NotImplemented))

    type: ClassVar[SchemaType] = NotImplemented
    format: Optional[str] = None
    enum: Optional[Tuple[Any, ...]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    default: Optional[Any] = None
    examples: Optional[List[Any]] = None
    readOnly: Optional[bool] = None
    writeOnly: Optional[bool] = None
    extensions: Optional[Tuple[frozendict.FrozenDict[str, Any], ...]] = None

    __repr = cached_property(filtered_repr)

    def __repr__(self) -> str:  # pragma: nocover
        return self.__repr

    @cached_property
    def __str(self) -> str:  # pragma: nocover
        fields = [f"type={self.type.value!r}"]
        for f in dataclasses.fields(self):
            val = getattr(self, f.name)
            if (val or val in {False, 0}) and f.repr:
                fields.append(f"{f.name}={val!r}")
        return f"({', '.join(fields)})"

    def __str__(self) -> str:  # pragma: nocover
        return self.__str

    @cached_property
    def validator(self) -> Callable:  # pragma: nocover
        """The JSON Schema validator.

        Notes
        -----
        If `fastjsonschema` is not installed, this will raise a ValueError.

        See Also
        --------
        `fastjsonschema <https://horejsek.github.io/python-fastjsonschema/>`_
        """
        if fastjsonschema:
            return fastjsonschema.compile(self.primitive())
        raise RuntimeError(
            "Can't compile validator, 'fastjsonschema' is not installed."
        )

    def validate(self, obj) -> Any:  # pragma: nocover
        """Validate an object against the defined JSON Schema."""
        try:
            return self.validator(obj)
        except (
            fastjsonschema.JsonSchemaException,
            fastjsonschema.JsonSchemaDefinitionException,
        ):
            raise ValueError(f"<{obj!r}> violates schema: {str(self)}") from None

    def copy(self):  # pragma: nocover
        """Return a new copy of this schema field."""
        return copy.deepcopy(self)


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class UndeclaredSchemaField(BaseSchemaField):
    """A sentinel object for generating an empty schema."""

    pass


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class MultiSchemaField(BaseSchemaField):
    """A schema field which supports multiple types."""

    anyOf: Optional[Tuple["SchemaFieldT", ...]] = None
    allOf: Optional[Tuple["SchemaFieldT", ...]] = None
    oneOf: Optional[Tuple["SchemaFieldT", ...]] = None


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class NullSchemaField(BaseSchemaField):
    type = SchemaType.NULL


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class StrSchemaField(BaseSchemaField):
    """A JSON Schema Field for the `string` type.

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


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class IntSchemaField(BaseSchemaField):
    """A JSON Schema Field for the `integer` type.

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


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class NumberSchemaField(IntSchemaField):
    """A JSON Schema Field for the `number` type.

    See Also
    --------
    `JSON Schema Numeric Types <https://json-schema.org/understanding-json-schema/reference/numeric.html>`_
    """

    type = SchemaType.NUM


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class BooleanSchemaField(BaseSchemaField):
    """A JSON Schema Field for the `boolean` type.

    See Also
    --------
    `JSON Schema Boolean Type <https://json-schema.org/understanding-json-schema/reference/boolean.html>`_
    """

    type = SchemaType.BOOL


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class ObjectSchemaField(BaseSchemaField):
    """A JSON Schema Field for the `object` type.

    See Also
    --------
    `JSON Schema Object Type <https://json-schema.org/understanding-json-schema/reference/object.html>`_
    """

    type = SchemaType.OBJ
    properties: Optional[Mapping[str, Any]] = None
    additionalProperties: Optional[Union[bool, Any]] = None
    maxProperties: Optional[int] = None
    minProperties: Optional[int] = None
    required: Optional[Collection] = None
    propertyNames: Optional[Mapping[str, Pattern]] = None
    patternProperties: Optional[Mapping[Pattern, Any]] = None
    dependencies: Optional[Mapping[str, Union[Tuple[str], Any]]] = None
    definitions: Optional[frozendict.FrozenDict[str, Any]] = None


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class ArraySchemaField(BaseSchemaField):
    """A JSON Schema Field for the `array` type.

    See Also
    --------
    `JSON Schema Array Type <https://json-schema.org/understanding-json-schema/reference/array.html>`_
    """

    type = SchemaType.ARR
    items: Optional[Any] = None
    contains: Optional[Any] = None
    additionalItems: Optional[bool] = None
    minItems: Optional[int] = None
    maxItems: Optional[int] = None
    uniqueItems: Optional[bool] = None


SchemaFieldT = Union[
    StrSchemaField,
    IntSchemaField,
    NumberSchemaField,
    BooleanSchemaField,
    ObjectSchemaField,
    ArraySchemaField,
    MultiSchemaField,
    UndeclaredSchemaField,
    NullSchemaField,
]
"""A type-alias for the defined JSON Schema Fields."""


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


SCHEMA_FIELD_FORMATS = TypeMap(
    {
        frozendict.FrozenDict: ObjectSchemaField(),
        decimal.Decimal: NumberSchemaField(),
        datetime.datetime: StrSchemaField(format=StringFormat.DTIME),
        pendulum.DateTime: StrSchemaField(format=StringFormat.DTIME),
        datetime.date: StrSchemaField(format=StringFormat.DATE),
        pendulum.Date: StrSchemaField(format=StringFormat.DATE),
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
        str: StrSchemaField(),
        AnyStr: StrSchemaField(),
        Text: StrSchemaField(),
        bytes: StrSchemaField(),
        bool: BooleanSchemaField(),
        int: IntSchemaField(),
        float: NumberSchemaField(),
        list: ArraySchemaField(),
        set: ArraySchemaField(uniqueItems=True),
        tuple: ArraySchemaField(additionalItems=False),
        frozenset: ArraySchemaField(uniqueItems=True, additionalItems=False),
        dict: ObjectSchemaField(),
        type(None): NullSchemaField(),
    }
)
