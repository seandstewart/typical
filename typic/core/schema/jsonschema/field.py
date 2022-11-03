from __future__ import annotations

import dataclasses
import datetime
import decimal
import enum
import inspect
import ipaddress
import numbers
import pathlib
import re
import reprlib
import uuid
from typing import (
    Any,
    AnyStr,
    ClassVar,
    Collection,
    Mapping,
    Pattern,
    Text,
    Tuple,
    Type,
    Union,
)

from typic import util
from typic.compat import Literal
from typic.core import constants, interfaces
from typic.types import dsn, email, frozendict, path, secret, url

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
)

slotted = util.slotted(dict=False, weakref=True)


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

    def __str__(self) -> str:
        return self.value

    def __repr__(self):
        return self.value.__repr__()


@slotted
@dataclasses.dataclass(frozen=True)
class Ref:
    """A JSON Schema ref (pointer).

    Usually for directing a validator to another schema definition.
    """

    __serde_flags__ = interfaces.SerdeFlags(fields={"ref": "$ref"}, exclude=("title",))

    title: str
    ref: str = dataclasses.field(init=False, repr=False)

    def __init__(self, title: str, *path: str):
        path = path or ("definitions",)
        pathstr = "/".join(path)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "ref", f"#/{pathstr}/{self.title}")


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
class BaseSchemaField:
    """The base JSON Schema Field."""

    __serde_flags__ = interfaces.SerdeFlags(
        fields=("type",),
        omit=(None, NotImplemented, inspect.Signature.empty, constants.empty),
    )

    type: ClassVar[SchemaType] = NotImplemented
    format: str | None = None
    enum: tuple[Any, ...] | None = None
    title: str | None = None
    description: str | None = None
    default: Any | Type[constants.empty] = constants.empty
    examples: list[Any] | None = None
    readOnly: bool | None = None
    writeOnly: bool | None = None
    extensions: tuple[frozendict.FrozenDict[str, SchemaFieldT], ...] | None = None

    @reprlib.recursive_repr()
    def __repr__(self) -> str:  # pragma: nocover
        vars = ", ".join(
            f"{f.name}={v!r}"
            for f in dataclasses.fields(self)
            if (v := getattr(self, f.name))
            not in (f.default, NotImplemented, constants.empty)
        )

        return f"{self.__class__.__name__}({vars})"


NestedSchemaT = Union[Ref, BaseSchemaField]


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class UndeclaredSchemaField(BaseSchemaField):
    """A sentinel object for generating an empty schema."""

    type = None


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class MultiSchemaField(BaseSchemaField):
    """A schema field which supports multiple types."""

    anyOf: tuple[SchemaFieldT, ...] | None = None
    allOf: tuple[SchemaFieldT, ...] | None = None
    oneOf: tuple[SchemaFieldT, ...] | None = None


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
    format: StringFormat | None = None
    pattern: Pattern | None = None
    minLength: int | None = None
    maxLength: int | None = None


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
    multipleOf: numbers.Number | None = None
    maximum: numbers.Number | None = None
    minimum: numbers.Number | None = None
    exclusiveMaximum: numbers.Number | None = None
    exclusiveMinimum: numbers.Number | None = None


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
    properties: _PropertiesT | None = None
    additionalProperties: Literal[False] | SchemaFieldT | None = None
    maxProperties: int | None = None
    minProperties: int | None = None
    required: Collection | None = None
    propertyNames: Mapping[str, Pattern] | None = None
    patternProperties: _PatternsT | None = None
    dependencies: _DependenciesT | None = None
    definitions: frozendict.FrozenDict[str, SchemaFieldT] | None = None


@slotted
@dataclasses.dataclass(frozen=True, repr=False)
class ArraySchemaField(BaseSchemaField):
    """A JSON Schema Field for the `array` type.

    See Also
    --------
    `JSON Schema Array Type <https://json-schema.org/understanding-json-schema/reference/array.html>`_
    """

    type = SchemaType.ARR
    prefixItems: tuple[SchemaFieldT, ...] | None = None
    items: SchemaFieldT | None = None
    contains: Any | None = None
    minItems: int | None = None
    maxItems: int | None = None
    minContains: int | None = None
    maxContains: int | None = None
    uniqueItems: bool | None = None


SchemaFieldT = Union[
    BaseSchemaField,
    StrSchemaField,
    IntSchemaField,
    NumberSchemaField,
    BooleanSchemaField,
    ObjectSchemaField,
    ArraySchemaField,
    MultiSchemaField,
    UndeclaredSchemaField,
    NullSchemaField,
    Ref,
]
"""A type-alias for the defined JSON Schema Fields."""

_PropertiesT = Union[Mapping[str, SchemaFieldT], Mapping[str, Ref]]
_PatternsT = Union[Mapping[Pattern, SchemaFieldT], Mapping[Pattern, Ref]]
_DependenciesT = Union[
    Mapping[str, Tuple[str]], Mapping[str, SchemaFieldT], Mapping[str, Ref]
]


SCHEMA_FIELD_FORMATS = util.TypeMap(
    {
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
        str: StrSchemaField(),
        AnyStr: StrSchemaField(),  # type: ignore
        Text: StrSchemaField(),
        bytes: StrSchemaField(),
        bool: BooleanSchemaField(),
        int: IntSchemaField(),
        float: NumberSchemaField(),
        list: ArraySchemaField(),
        set: ArraySchemaField(uniqueItems=True),
        tuple: ArraySchemaField(),
        frozenset: ArraySchemaField(uniqueItems=True),
        dict: ObjectSchemaField(),
        type(None): NullSchemaField(),
        Literal: BaseSchemaField(),  # type: ignore
        numbers.Number: NumberSchemaField(),
    }
)
