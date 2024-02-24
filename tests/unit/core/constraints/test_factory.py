from __future__ import annotations

import dataclasses
import decimal
import enum
import inspect
import typing

import pytest

from typical.constraints import factory
from typical.constraints.core import structs, validators
from typical.core import constants


class MyEnum(enum.IntEnum):
    one = enum.auto()
    two = enum.auto()


@dataclasses.dataclass
class MyClass:
    foo: str


class MyDict(typing.TypedDict):
    foo: str


class MyTup(typing.NamedTuple):
    foo: str


Tup = typing.Tuple[str, int]


@pytest.mark.suite(
    anytype=dict(
        given_type=typing.Any,
        given_context=dict(),
        expected_constraints_cls=structs.UndeclaredTypeConstraints,
        expected_validator_cls=validators.NoOpInstanceValidator,
    ),
    constants_empty=dict(
        given_type=constants.empty,
        given_context=dict(),
        expected_constraints_cls=structs.UndeclaredTypeConstraints,
        expected_validator_cls=validators.NoOpInstanceValidator,
    ),
    param_empty=dict(
        given_type=inspect.Parameter.empty,
        given_context=dict(),
        expected_constraints_cls=structs.UndeclaredTypeConstraints,
        expected_validator_cls=validators.NoOpInstanceValidator,
    ),
    ellipsis=dict(
        given_type=Ellipsis,
        given_context=dict(),
        expected_constraints_cls=structs.UndeclaredTypeConstraints,
        expected_validator_cls=validators.NoOpInstanceValidator,
    ),
    enum=dict(
        given_type=MyEnum,
        given_context=dict(),
        expected_constraints_cls=structs.EnumerationConstraints,
        expected_validator_cls=validators.OneOfValidator,
    ),
    literal=dict(
        given_type=typing.Literal[1, 2],
        given_context=dict(),
        expected_constraints_cls=structs.EnumerationConstraints,
        expected_validator_cls=validators.OneOfValidator,
    ),
    string=dict(
        given_type=str,
        given_context=dict(),
        expected_constraints_cls=structs.TextConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    bytestring=dict(
        given_type=bytes,
        given_context=dict(),
        expected_constraints_cls=structs.TextConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    boolean=dict(
        given_type=bool,
        given_context=dict(),
        expected_constraints_cls=structs.TypeConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    integer=dict(
        given_type=int,
        given_context=dict(),
        expected_constraints_cls=structs.NumberConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    float=dict(
        given_type=float,
        given_context=dict(),
        expected_constraints_cls=structs.NumberConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    decimal=dict(
        given_type=decimal.Decimal,
        given_context=dict(),
        expected_constraints_cls=structs.DecimalConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    structured=dict(
        given_type=MyClass,
        given_context=dict(),
        expected_constraints_cls=structs.StructuredObjectConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    structured_dict=dict(
        given_type=MyDict,
        given_context=dict(),
        expected_constraints_cls=structs.StructuredObjectConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    structured_ntup=dict(
        given_type=MyTup,
        given_context=dict(),
        expected_constraints_cls=structs.StructuredObjectConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    structured_tup=dict(
        given_type=Tup,
        given_context=dict(),
        expected_constraints_cls=structs.ArrayConstraints,
        expected_validator_cls=validators.NotInstanceAssertionsValidator,
    ),
    dict=dict(
        given_type=dict,
        given_context=dict(),
        expected_constraints_cls=structs.MappingConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    mapping=dict(
        given_type=typing.Mapping,
        given_context=dict(),
        expected_constraints_cls=structs.MappingConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    collection=dict(
        given_type=typing.Collection,
        given_context=dict(),
        expected_constraints_cls=structs.ArrayConstraints,
        expected_validator_cls=validators.IsInstanceValidator,
    ),
    optional=dict(
        given_type=typing.Optional[str],
        given_context=dict(),
        expected_constraints_cls=structs.TextConstraints,
        expected_validator_cls=validators.NullableIsInstanceValidator,
    ),
)
def test_build(
    given_type, given_context, expected_constraints_cls, expected_validator_cls
):
    # When
    built_cv = factory.build(t=given_type, **given_context)
    # Then
    assert isinstance(built_cv.constraints, expected_constraints_cls)
    assert isinstance(built_cv.validator, expected_validator_cls)


def test_build_forwardref():
    # Given
    given_type = "dict | None"
    expected_constraints_cls = structs.MappingConstraints
    expected_validator_cls = validators.NullableIsInstanceValidator
    # When
    built_dcv = factory.build(t=given_type)
    built_cv = built_dcv.cv
    # Then
    assert isinstance(built_cv.constraints, expected_constraints_cls)
    assert isinstance(built_cv.validator, expected_validator_cls)
