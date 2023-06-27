from __future__ import annotations

import dataclasses
import decimal
import enum
import inspect
import typing

import pytest

from typical.core import constants
from typical.core.constraints import error, factory


class MyEnum(enum.IntEnum):
    one = enum.auto()
    two = enum.auto()


@dataclasses.dataclass
class MyClass:
    tag: typing.ClassVar[int] = 1
    foo: str


@dataclasses.dataclass
class MyOtherClass:
    tag: typing.ClassVar[int] = 2
    bar: str


class MyDict(typing.TypedDict):
    foo: str


class MyTup(typing.NamedTuple):
    foo: str


Tup = typing.Tuple[str, int]


@pytest.mark.suite(
    anytype=dict(
        given_type=typing.Any,
        given_context=dict(),
        given_value=1,
    ),
    constants_empty=dict(
        given_type=constants.empty,
        given_context=dict(),
        given_value=1,
    ),
    param_empty=dict(
        given_type=inspect.Parameter.empty,
        given_context=dict(),
        given_value=1,
    ),
    ellipsis=dict(
        given_type=Ellipsis,
        given_context=dict(),
        given_value=1,
    ),
    enum=dict(
        given_type=MyEnum,
        given_context=dict(),
        given_value=1,
    ),
    literal=dict(
        given_type=typing.Literal[1, 2],
        given_context=dict(),
        given_value=1,
    ),
    string=dict(given_type=str, given_context=dict(), given_value="1"),
    bytestring=dict(
        given_type=bytes,
        given_context=dict(),
        given_value=b"1",
    ),
    boolean=dict(
        given_type=bool,
        given_context=dict(),
        given_value=True,
    ),
    integer=dict(
        given_type=int,
        given_context=dict(),
        given_value=1,
    ),
    float=dict(
        given_type=float,
        given_context=dict(),
        given_value=1.0,
    ),
    decimal=dict(
        given_type=decimal.Decimal, given_context=dict(), given_value=decimal.Decimal(1)
    ),
    structured=dict(
        given_type=MyClass, given_context=dict(), given_value={"foo": "bar"}
    ),
    structured_dict=dict(
        given_type=MyDict, given_context=dict(), given_value={"foo": "bar"}
    ),
    structured_ntuple=dict(
        given_type=MyTup, given_context=dict(), given_value={"foo": "bar"}
    ),
    structured_tuple=dict(
        given_type=Tup,
        given_context=dict(),
        given_value=("bar", 1),
    ),
    dict=dict(
        given_type=dict,
        given_context=dict(),
        given_value={},
    ),
    mapping=dict(
        given_type=typing.Mapping,
        given_context=dict(),
        given_value={},
    ),
    mapping_entries=dict(
        given_type=typing.Mapping[str, int],
        given_context=dict(),
        given_value={"foo": 1},
    ),
    collection=dict(
        given_type=typing.Collection,
        given_context=dict(),
        given_value=[],
    ),
    collection_entries=dict(
        given_type=typing.Collection[str],
        given_context=dict(),
        given_value=["foo"],
    ),
    optional=dict(
        given_type=typing.Optional[str],
        given_context=dict(),
        given_value="foo",
    ),
    optional_null=dict(
        given_type=typing.Optional[str],
        given_context=dict(),
        given_value=None,
    ),
    union=dict(
        given_type=typing.Union[str, int],
        given_context=dict(),
        given_value=1,
    ),
    union_nullable=dict(
        given_type=typing.Union[str, int, None],
        given_context=dict(),
        given_value=1,
    ),
    union_nullable_null=dict(
        given_type=typing.Union[str, int, None],
        given_context=dict(),
        given_value=None,
    ),
    tagged_union=dict(
        given_type=typing.Union[MyClass, MyOtherClass],
        given_context=dict(),
        given_value={"foo": "bar", "tag": 1},
    ),
    tagged_union_nullable=dict(
        given_type=typing.Union[MyClass, MyOtherClass, None],
        given_context=dict(),
        given_value={"bar": "foo", "tag": 2},
    ),
    tagged_union_nullable_null=dict(
        given_type=typing.Union[MyClass, MyOtherClass, None],
        given_context=dict(),
        given_value=None,
    ),
)
def test_validation_valid(given_type, given_context, given_value):
    # When
    built_cv = factory.build(t=given_type, **given_context)
    validated = built_cv.validate(given_value)
    # Then
    assert validated == given_value


@pytest.mark.suite(
    enum=dict(
        given_type=MyEnum,
        given_context=dict(),
        given_value=3,
    ),
    literal=dict(
        given_type=typing.Literal[1, 2],
        given_context=dict(),
        given_value=3,
    ),
    string=dict(
        given_type=str,
        given_context=dict(),
        given_value=1,
    ),
    bytestring=dict(
        given_type=bytes,
        given_context=dict(),
        given_value="1",
    ),
    boolean=dict(
        given_type=bool,
        given_context=dict(),
        given_value="true",
    ),
    integer=dict(
        given_type=int,
        given_context=dict(),
        given_value="1",
    ),
    float=dict(
        given_type=float,
        given_context=dict(),
        given_value="1.0",
    ),
    decimal=dict(
        given_type=decimal.Decimal,
        given_context=dict(),
        given_value="1",
    ),
    structured=dict(given_type=MyClass, given_context=dict(), given_value={}),
    structured_dict_missing_field=dict(
        given_type=MyDict, given_context=dict(), given_value={}
    ),
    structured_dict_field_type=dict(
        given_type=MyDict,
        given_context=dict(),
        given_value={"foo": 1},
    ),
    structured_ntuple_missing_field=dict(
        given_type=MyTup, given_context=dict(), given_value={}
    ),
    structured_ntuple_field_type=dict(
        given_type=MyTup,
        given_context=dict(),
        given_value={"foo": 1},
    ),
    structured_tuple_short=dict(
        given_type=Tup,
        given_context=dict(),
        given_value=("bar",),
    ),
    structured_tuple_type=dict(
        given_type=Tup,
        given_context=dict(),
        given_value=("bar", "blah"),
    ),
    dict=dict(
        given_type=dict,
        given_context=dict(),
        given_value=[],
    ),
    mapping=dict(
        given_type=typing.Mapping,
        given_context=dict(),
        given_value=[],
    ),
    mapping_entries=dict(
        given_type=typing.Mapping[str, int],
        given_context=dict(),
        given_value={"foo": "foo"},
    ),
    mapping_entries_field=dict(
        given_type=typing.Mapping[str, int],
        given_context=dict(),
        given_value={1: "foo"},
    ),
    collection=dict(
        given_type=typing.Collection,
        given_context=dict(),
        given_value=1,
    ),
    collection_entries=dict(
        given_type=typing.Collection[str],
        given_context=dict(),
        given_value=[1],
    ),
    optional=dict(
        given_type=typing.Optional[str],
        given_context=dict(),
        given_value=1,
    ),
    union=dict(
        given_type=typing.Union[str, int],
        given_context=dict(),
        given_value=b"1",
    ),
    union_nullable=dict(
        given_type=typing.Union[str, int, None],
        given_context=dict(),
        given_value=b"1",
    ),
    tagged_union_no_tag=dict(
        given_type=typing.Union[MyClass, MyOtherClass],
        given_context=dict(),
        given_value={"foo": "bar"},
    ),
    tagged_union_nullable_field_type=dict(
        given_type=typing.Union[MyClass, MyOtherClass, None],
        given_context=dict(),
        given_value={"bar": 1, "tag": 2},
    ),
)
def test_validation_invalid(given_type, given_context, given_value):
    # When
    built_cv = factory.build(t=given_type, **given_context)
    # Then
    with pytest.raises(error.ConstraintValueError):
        built_cv.validate(given_value)


@pytest.mark.suite(
    enum=dict(
        given_type=MyEnum,
        given_context=dict(),
        given_value=3,
    ),
    literal=dict(
        given_type=typing.Literal[1, 2],
        given_context=dict(),
        given_value=3,
    ),
    string=dict(
        given_type=str,
        given_context=dict(),
        given_value=1,
    ),
    bytestring=dict(
        given_type=bytes,
        given_context=dict(),
        given_value="1",
    ),
    boolean=dict(
        given_type=bool,
        given_context=dict(),
        given_value="true",
    ),
    integer=dict(
        given_type=int,
        given_context=dict(),
        given_value="1",
    ),
    float=dict(
        given_type=float,
        given_context=dict(),
        given_value="1.0",
    ),
    decimal=dict(
        given_type=decimal.Decimal,
        given_context=dict(),
        given_value="1",
    ),
    structured=dict(given_type=MyClass, given_context=dict(), given_value={}),
    structured_dict_missing_field=dict(
        given_type=MyDict, given_context=dict(), given_value={}
    ),
    structured_dict_field_type=dict(
        given_type=MyDict,
        given_context=dict(),
        given_value={"foo": 1},
    ),
    structured_ntuple_missing_field=dict(
        given_type=MyTup, given_context=dict(), given_value={}
    ),
    structured_ntuple_field_type=dict(
        given_type=MyTup,
        given_context=dict(),
        given_value={"foo": 1},
    ),
    structured_tuple_short=dict(
        given_type=Tup,
        given_context=dict(),
        given_value=("bar",),
    ),
    structured_tuple_type=dict(
        given_type=Tup,
        given_context=dict(),
        given_value=("bar", "blah"),
    ),
    dict=dict(
        given_type=dict,
        given_context=dict(),
        given_value=[],
    ),
    mapping=dict(
        given_type=typing.Mapping,
        given_context=dict(),
        given_value=[],
    ),
    mapping_entries=dict(
        given_type=typing.Mapping[str, int],
        given_context=dict(),
        given_value={"foo": "foo"},
    ),
    mapping_entries_field=dict(
        given_type=typing.Mapping[str, int],
        given_context=dict(),
        given_value={1: "foo"},
    ),
    collection=dict(
        given_type=typing.Collection,
        given_context=dict(),
        given_value=1,
    ),
    collection_entries=dict(
        given_type=typing.Collection[str],
        given_context=dict(),
        given_value=[1],
    ),
    optional=dict(
        given_type=typing.Optional[str],
        given_context=dict(),
        given_value=1,
    ),
    union=dict(
        given_type=typing.Union[str, int],
        given_context=dict(),
        given_value=b"1",
    ),
    union_nullable=dict(
        given_type=typing.Union[str, int, None],
        given_context=dict(),
        given_value=b"1",
    ),
    tagged_union_no_tag=dict(
        given_type=typing.Union[MyClass, MyOtherClass],
        given_context=dict(),
        given_value={"foo": "bar"},
    ),
    tagged_union_nullable_field_type=dict(
        given_type=typing.Union[MyClass, MyOtherClass, None],
        given_context=dict(),
        given_value={"bar": 1, "tag": 2},
    ),
)
def test_validation_invalid_exhaustive(given_type, given_context, given_value):
    # When
    built_cv = factory.build(t=given_type, **given_context)
    result = built_cv.validate(given_value, path="test", exhaustive=True)
    if isinstance(result, dict):
        result = result.popitem()[-1]

    # Then
    assert isinstance(result, error.ConstraintValueError)
