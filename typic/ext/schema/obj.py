#!/usr/bin/env python
import copy
import dataclasses
import decimal
import enum
from typing import (
    ClassVar,
    Collection,
    List,
    Mapping,
    Any,
    Union,
    Callable,
    Tuple,
    Pattern,
    Optional,
)

from typic.json import dumps
from typic.serde.obj import SerdeFlags
from typic.serde.resolver import resolver
from typic.util import filtered_repr, cached_property
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


@dataclasses.dataclass(frozen=True)
class Ref:
    """A JSON Schema ref (pointer).

    Usually for directing a validator to another schema definition.
    """

    __serde_flags__ = SerdeFlags(fields={"ref": "$ref"})

    ref: str

    def primitive(self):
        return resolver.primitive(self)


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


@dataclasses.dataclass(frozen=True, repr=False)
class BaseSchemaField:
    """The base JSON Schema Field."""

    __serde_flags__ = SerdeFlags(omit=(None, NotImplemented))

    type: ClassVar[SchemaType] = NotImplemented
    format: Optional[str] = None
    enum: Optional[Tuple[Any, ...]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    default: Optional[str] = None
    examples: Optional[List[Any]] = None
    readOnly: Optional[bool] = None
    writeOnly: Optional[bool] = None
    extensions: Optional[Tuple[Mapping[str, Any], ...]] = None

    def primitive(self, *, lazy: bool = False) -> Mapping[str, Any]:
        return resolver.primitive(self, lazy=lazy)

    def json(self, *, indent: int = 0, ensure_ascii: bool = False) -> str:
        return dumps(
            self.primitive(lazy=True), indent=indent, ensure_ascii=ensure_ascii
        )

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
        If ``fastjsonschema`` is not installed, this will raise a ValueError.

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


@dataclasses.dataclass(frozen=True, repr=False)
class UndeclaredSchemaField(BaseSchemaField):
    """A sentinel object for generating an empty schema."""

    pass


@dataclasses.dataclass(frozen=True, repr=False)
class MultiSchemaField(BaseSchemaField):
    """A schema field which supports multiple types."""

    anyOf: Optional[Tuple["SchemaFieldT", ...]] = None
    allOf: Optional[Tuple["SchemaFieldT", ...]] = None
    oneOf: Optional[Tuple["SchemaFieldT", ...]] = None


@dataclasses.dataclass(frozen=True, repr=False)
class NullSchemaField(BaseSchemaField):
    type = SchemaType.NULL


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


@dataclasses.dataclass(frozen=True, repr=False)
class ObjectSchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``object`` type.

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
    definitions: Optional[Mapping[str, Any]] = None


@dataclasses.dataclass(frozen=True, repr=False)
class ArraySchemaField(BaseSchemaField):
    """A JSON Schema Field for the ``array`` type.

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
