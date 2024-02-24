from __future__ import annotations

import dataclasses
import inspect
import sys
import typing
import typing as t

import pytest

from typical import inspection


class MyClass: ...


@pytest.mark.suite(
    dict=dict(annotation=dict, expected=dict),
    list=dict(annotation=list, expected=list),
    tuple=dict(annotation=tuple, expected=tuple),
    set=dict(annotation=set, expected=set),
    frozenset=dict(annotation=frozenset, expected=frozenset),
    generic_dict=dict(annotation=t.Dict, expected=dict),
    generic_list=dict(annotation=t.List, expected=list),
    generic_tuple=dict(annotation=t.Tuple, expected=tuple),
    generic_set=dict(annotation=t.Set, expected=set),
    generic_frozenset=dict(annotation=t.FrozenSet, expected=frozenset),
    function=dict(annotation=lambda x: x, expected=t.Callable),
    newtype=dict(annotation=t.NewType("new", dict), expected=dict),
    subscripted_generic=dict(annotation=t.Dict[str, str], expected=dict),
    user_type=dict(annotation=MyClass, expected=MyClass),
)
def test_origin(annotation, expected):
    # When
    actual = inspection.origin(annotation)
    # Then
    assert actual == expected


UnBoundT = t.TypeVar("UnBoundT")
BoundT = t.TypeVar("BoundT", bound=int)
ConstrainedT = t.TypeVar("ConstrainedT", str, int)


@pytest.mark.suite(
    dict=dict(annotation=dict, expected=()),
    subscripted_dict=dict(annotation=t.Dict[str, str], expected=(str, str)),
    dict_unbound_tvar=dict(annotation=t.Dict[str, UnBoundT], expected=(str, t.Any)),
    dict_bound_tvar=dict(annotation=t.Dict[str, BoundT], expected=(str, int)),
    dict_constrained_tvar=dict(
        annotation=t.Dict[str, ConstrainedT], expected=(str, t.Union[str, int])
    ),
)
def test_get_args(annotation, expected):
    # When
    actual = inspection.get_args(annotation)
    # Then
    assert actual == expected


@pytest.mark.suite(
    builtin_dict=dict(annotation=dict, expected="dict"),
    generic_dict=dict(annotation=t.Dict, expected="Dict"),
    subscripted_dict=dict(annotation=t.Dict[str, str], expected="Dict"),
    user_class=dict(annotation=MyClass, expected=MyClass.__name__),
)
def test_get_name(annotation, expected):
    # When
    actual = inspection.get_name(annotation)
    # Then
    assert actual == expected


@pytest.mark.suite(
    builtin_dict=dict(annotation=dict, expected="dict"),
    generic_dict=dict(annotation=t.Dict, expected="typing.Dict"),
    subscripted_dict=dict(annotation=t.Dict[str, str], expected="typing.Dict"),
    user_class=dict(annotation=MyClass, expected=MyClass.__qualname__),
)
def test_get_qualname(annotation, expected):
    # When
    actual = inspection.get_qualname(annotation)
    # Then
    assert actual == expected


def test_resolve_supertype():
    # Given
    supertype = int
    UserID = t.NewType("UserID", int)
    AdminID = t.NewType("AdminID", UserID)
    # When
    resolved = inspection.resolve_supertype(AdminID)
    # Then
    assert resolved == supertype


@dataclasses.dataclass
class FieldClass:
    field: str = None


class TotalFieldDict(t.TypedDict):
    field: str


class FieldDict(t.TypedDict, total=False):
    field: str


class FieldTuple(t.NamedTuple):
    field: str = None


StructuredTuple = t.Tuple[str]
VarTuple = t.Tuple[str, ...]


@pytest.mark.skipif(sys.version_info < (3, 9), reason="3.8 doesn't handle ForwardRef.")
@pytest.mark.suite(
    user_class=dict(
        annotation=FieldClass,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="field",
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=None,
                    annotation="str",
                ),
            ),
            return_annotation=None,
        ),
    ),
    total_typed_dict=dict(
        annotation=TotalFieldDict,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="field",
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    annotation=str,
                ),
            )
        ),
    ),
    typed_dict=dict(
        annotation=FieldDict,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="field",
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=...,
                    annotation=str,
                ),
            )
        ),
    ),
    named_tuple=dict(
        annotation=FieldTuple,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="field",
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=None,
                    annotation=typing.ForwardRef("str"),
                ),
            )
        ),
    ),
    structured_tuple=dict(
        annotation=StructuredTuple,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="arg0",
                    kind=inspect.Parameter.POSITIONAL_ONLY,
                    annotation=str,
                ),
            )
        ),
    ),
    var_tuple=dict(
        annotation=VarTuple,
        expected=inspect.Signature(
            parameters=(
                inspect.Parameter(
                    name="args",
                    kind=inspect.Parameter.VAR_POSITIONAL,
                    annotation=str,
                ),
            )
        ),
    ),
)
def test_signature(annotation, expected):
    # When
    actual = inspection.signature(annotation)
    # Then
    assert actual == expected
