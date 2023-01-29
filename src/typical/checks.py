from __future__ import annotations

import abc
import builtins
import collections
import dataclasses
import datetime
import decimal
import enum
import functools
import inspect
import ipaddress
import numbers
import pathlib
import sqlite3
import types
import uuid
from operator import attrgetter
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Collection,
    Generic,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

import typical.core.strict as strict
import typical.inspection as inspection
from typical.compat import (
    Final,
    ForwardRef,
    Literal,
    Protocol,
    Record,
    TypeGuard,
    lru_cache,
)
from typical.core.annotations import ReadOnly, WriteOnly

if TYPE_CHECKING:
    from typical.core.constraints import AbstractConstraintValidator
    from typical.magic.typed import TypicObjectT

ObjectT = TypeVar("ObjectT")
"""A type-alias for a python object.

Used in place of :py:class:`Any` for better type-hinting.

Examples
--------
>>> import typic
>>> from typing import type
>>> def get_type(obj: typic.ObjectT) -> type[ObjectT]:
...     return type(obj)
...
>>> get_type("")  # IDE/mypy tracks input type
str
"""

__all__ = (
    "BUILTIN_TYPES",
    "ObjectT",
    "isabstract",
    "isbuiltininstance",
    "isbuiltintype",
    "isbuiltinsubtype",
    "isclassvartype",
    "iscollectiontype",
    "isconstrained",
    "isdatetype",
    "isdecimaltype",
    "isdescriptor",
    "isenumtype",
    "isfinal",
    "isfixedtuple",
    "isforwardref",
    "isfromdictclass",
    "isfrozendataclass",
    "isgeneric",
    "ishashable",
    "isinstance",
    "isiterabletype",
    "isliteral",
    "ismappingtype",
    "isnamedtuple",
    "isoptionaltype",
    "isproperty",
    "isreadonly",
    "issimpleattribute",
    "isstrict",
    "isstdlibinstance",
    "isstdlibtype",
    "isstdlibsubtype",
    "issubclass",
    "istexttype",
    "istimetype",
    "istimedeltatype",
    "istupletype",
    "istypeddict",
    "istypedtuple",
    "isuniontype",
    "isuuidtype",
    "iswriteonly",
    "should_unwrap",
)


# Here we are with a manually-defined set of builtin-types.
# This probably won't break anytime soon, but we shall see...
BuiltInTypeT = Union[
    int, bool, float, str, bytes, bytearray, list, set, frozenset, tuple, dict, None
]
BUILTIN_TYPES = frozenset(
    (type(None), *(t for t in BuiltInTypeT.__args__ if t is not None))  # type: ignore
)
BUILTIN_TYPES_TUPLE = tuple(BUILTIN_TYPES)
STDLibTypeT = Union[
    BuiltInTypeT,
    datetime.datetime,
    datetime.date,
    datetime.timedelta,
    datetime.time,
    decimal.Decimal,
    ipaddress.IPv4Address,
    ipaddress.IPv6Address,
    pathlib.Path,
    uuid.UUID,
    collections.defaultdict,
    collections.deque,
    types.MappingProxyType,
]
STDLIB_TYPES = frozenset(
    (type(None), *(t for t in STDLibTypeT.__args__ if t is not None))  # type: ignore
)
STDLIB_TYPES_TUPLE = tuple(STDLIB_TYPES)


@lru_cache(maxsize=None)
def isbuiltintype(
    obj: type[ObjectT] | types.FunctionType,
) -> TypeGuard[type[BuiltInTypeT]]:
    """Check whether the provided object is a builtin-type.

    Notes:
        Python stdlib and Python documentation have no "definitive list" of
        builtin-**types**, despite the fact that they are well-known. The closest we have
        is https://docs.python.org/3.7/library/functions.html, which clumps the
        builtin-types with builtin-functions. Despite clumping these types with functions
        in the documentation, these types eval as False when compared to
        :py:class:`types.BuiltinFunctionType`, which is meant to be an alias for the
        builtin-functions listed in the documentation.

        All this to say, here we are with a custom check to determine whether a type is a
        builtin.

    Examples:
        >>> from typical import checks
        >>> from typing import NewType, Mapping
        >>> checks.isbuiltintype(str)
        True
        >>> checks.isbuiltintype(NewType("MyStr", str))
        True
        >>> class Foo: ...
        ...
        >>> checks.isbuiltintype(Foo)
        False
        >>> checks.isbuiltintype(Mapping)
        False
    """
    return (
        inspection.resolve_supertype(obj) in BUILTIN_TYPES
        or inspection.resolve_supertype(type(obj)) in BUILTIN_TYPES
    )


@lru_cache(maxsize=None)
def isstdlibtype(obj: type[ObjectT]) -> TypeGuard[type[STDLibTypeT]]:
    return (
        inspection.resolve_supertype(obj) in STDLIB_TYPES
        or inspection.resolve_supertype(type(obj)) in STDLIB_TYPES
    )


@lru_cache(maxsize=None)
def isbuiltinsubtype(t: type[ObjectT]) -> TypeGuard[type[BuiltInTypeT]]:
    """Check whether the provided type is a subclass of a builtin-type.

    Examples:
        >>> from typical import checks
        >>> from typing import NewType, Mapping
        >>> class SuperStr(str): ...
        ...
        >>> checks.isbuiltinsubtype(SuperStr)
        True
        >>> checks.isbuiltinsubtype(NewType("MyStr", SuperStr))
        True
        >>> class Foo: ...
        ...
        >>> checks.isbuiltintype(Foo)
        False
        >>> checks.isbuiltintype(Mapping)
        False
    """
    return issubclass(inspection.resolve_supertype(t), BUILTIN_TYPES_TUPLE)


@lru_cache(maxsize=None)
def isstdlibsubtype(t: type[ObjectT]) -> TypeGuard[type[STDLibTypeT]]:
    """Test whether the given type is a subclass of a standard-lib type.

    Examples:
        >>> import datetime
        >>> from typical import checks
        >>> class MyDate(datetime.date): ...
        ...
        >>> checks.isstdlibsubtype(MyDate)
        True
    """
    return issubclass(inspection.resolve_supertype(t), STDLIB_TYPES_TUPLE)


def isbuiltininstance(o: ObjectT) -> TypeGuard[BuiltInTypeT]:
    """Test whether an object is an instance of a builtin type.

    Examples:
        >>> from typical import checks
        >>> checks.isbuiltininstance("")
        True
    """
    return builtins.isinstance(o, BUILTIN_TYPES_TUPLE)


def isstdlibinstance(o: ObjectT) -> TypeGuard[STDLibTypeT]:
    """Test whether an object is an instance of a type in the standard-lib."""
    return builtins.isinstance(o, STDLIB_TYPES_TUPLE)


@lru_cache(maxsize=None)
def isoptionaltype(obj: type[ObjectT]) -> TypeGuard[Optional[ObjectT]]:
    """Test whether an annotation is :py:class`typing.Optional`, or can be treated as.

    :py:class:`typing.Optional` is an alias for `typing.Union[<T>, None]`, so both are
    "optional".

    Examples:
        >>> from typical import checks
        >>> from typing import Optional, Union, Dict, Literal
        >>> checks.isoptionaltype(Optional[str])
        True
        >>> checks.isoptionaltype(Union[str, None])
        True
        >>> checks.isoptionaltype(Literal["", None])
        True
        >>> checks.isoptionaltype(Dict[str, None])
    False
    """
    args = getattr(obj, "__args__", ())
    tname = inspection.get_name(inspection.origin(obj))
    nullarg = next((a for a in args if a in (type(None), None)), ...)
    isoptional = tname == "Optional" or (
        nullarg is not ... and tname in ("Union", "UnionType", "Literal")
    )
    return isoptional


@lru_cache(maxsize=None)
def isuniontype(obj: type[ObjectT]) -> TypeGuard[Union]:
    return inspection.get_name(inspection.origin(obj)) in ("Union", "UnionType")


@lru_cache(maxsize=None)
def isreadonly(obj: type[ObjectT]) -> TypeGuard[ReadOnly]:
    """Test whether an annotation is marked as :py:class:`typic.ReadOnly`

    Examples:
        >>> from typical import checks
        >>> from typical.core.annotations import ReadOnly
        >>> from typing import NewType
        >>> checks.isreadonly(ReadOnly[str])
        True
        >>> checks.isreadonly(NewType("Foo", ReadOnly[str]))
        True
    """
    return inspection.origin(obj) in (ReadOnly, Final) or isclassvartype(obj)


@lru_cache(maxsize=None)
def isfinal(obj: type[ObjectT]) -> bool:
    """Test whether an annotation is :py:class:`typing.Final`.

    Examples:
        >>> from typical import checks
        >>> from typing import NewType
        >>> from typical.compat import Final
        >>> checks.isfinal(Final[str])
        True
        >>> checks.isfinal(NewType("Foo", Final[str]))
        True
    """
    return inspection.origin(obj) is Final


@lru_cache(maxsize=None)
def isliteral(obj) -> bool:
    """Test whether an annotation is :py:class:`typing.Literal`.

    Examples:
        >>> from typical import checks
        >>>
    """
    return inspection.origin(obj) is Literal or (
        obj.__class__ is ForwardRef and obj.__forward_arg__.startswith("Literal")
    )


@lru_cache(maxsize=None)
def iswriteonly(obj: type[ObjectT]) -> TypeGuard[WriteOnly]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Examples:
        >>> from typical import checks
        >>> from typical.core.annotations import WriteOnly
        >>> from typing import NewType
        >>> checks.iswriteonly(WriteOnly[str])
        True
        >>> checks.iswriteonly(NewType("Foo", WriteOnly[str]))
        True
    """
    return inspection.origin(obj) is WriteOnly


@lru_cache(maxsize=None)
def isstrict(obj: type[ObjectT]) -> TypeGuard[strict.Strict]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Examples:
        >>> from typical import checks
        >>> from typical.core.strict import Strict
        >>> from typing import NewType
        >>> checks.isstrict(Strict[str])
        True
        >>> checks.isstrict(NewType("Foo", Strict[str]))
        True
    """
    return inspection.origin(obj) is strict.Strict


@lru_cache(maxsize=None)
def isdatetype(
    obj: type[ObjectT],
) -> TypeGuard[type[Union[datetime.datetime, datetime.date]]]:
    """Test whether this annotation is a a date/datetime object.

    Examples:
        >>> from typical import checks
        >>> import datetime
        >>> from typing import NewType
        >>> checks.isdatetype(datetime.datetime)
        True
        >>> checks.isdatetype(datetime.date)
        True
        >>> checks.isdatetype(NewType("Foo", datetime.datetime))
        True
    """
    return builtins.issubclass(inspection.origin(obj), datetime.date)


@lru_cache(maxsize=None)
def isdatetimetype(
    obj: type[ObjectT],
) -> TypeGuard[type[Union[datetime.datetime, datetime.date]]]:
    """Test whether this annotation is a a date/datetime object.

    Examples:
        >>> from typical import checks
        >>> import datetime
        >>> from typing import NewType
        >>> checks.isdatetype(datetime.datetime)
        True
        >>> checks.isdatetype(datetime.date)
        True
        >>> checks.isdatetype(NewType("Foo", datetime.datetime))
        True
    """
    return builtins.issubclass(inspection.origin(obj), datetime.datetime)


@lru_cache(maxsize=None)
def istimetype(obj: type[ObjectT]) -> TypeGuard[type[datetime.time]]:
    """Test whether this annotation is a a date/datetime object.

    Examples:
        >>> from typical import checks
        >>> import datetime
        >>> from typing import NewType
        >>> checks.istimetype(datetime.time)
        True
        >>> checks.istimetype(NewType("Foo", datetime.time))
        True
    """
    return builtins.issubclass(inspection.origin(obj), datetime.time)


@lru_cache(maxsize=None)
def istimedeltatype(obj: type[ObjectT]) -> TypeGuard[type[datetime.timedelta]]:
    """Test whether this annotation is a a date/datetime object.

    Examples:
        >>> from typical import checks
        >>> import datetime
        >>> from typing import NewType
        >>> checks.istimedeltatype(datetime.timedelta)
        True
        >>> checks.istimedeltatype(NewType("Foo", datetime.timedelta))
        True
    """
    return builtins.issubclass(inspection.origin(obj), datetime.timedelta)


@lru_cache(maxsize=None)
def isdecimaltype(obj: type[ObjectT]) -> TypeGuard[type[decimal.Decimal]]:
    """Test whether this annotation is a Decimal object.

    Examples:
        >>> from typical import checks
        >>> import decimal
        >>> from typing import NewType
        >>> checks.isdecimaltype(decimal.Decimal)
        True
        >>> checks.isdecimaltype(NewType("Foo", decimal.Decimal))
        True
    """
    return builtins.issubclass(inspection.origin(obj), decimal.Decimal)


@lru_cache(maxsize=None)
def isuuidtype(obj: type[ObjectT]) -> TypeGuard[type[uuid.UUID]]:
    """Test whether this annotation is a a date/datetime object.

    Examples:
        >>> from typical import checks
        >>> import uuid
        >>> from typing import NewType
        >>> checks.isuuidtype(uuid.UUID)
        True
        >>> class MyUUID(uuid.UUID): ...
        ...
        >>> checks.isuuidtype(MyUUID)
        True
        >>> checks.isuuidtype(NewType("Foo", uuid.UUID))
        True
    """
    return builtins.issubclass(inspection.origin(obj), uuid.UUID)


_COLLECTIONS = {list, set, tuple, frozenset, dict, str, bytes}


@lru_cache(maxsize=None)
def isiterabletype(obj: type[ObjectT]) -> TypeGuard[type[Iterable]]:
    """Test whether the given type is iterable.

    Examples:
        >>> from typical import checks
        >>> from typing import Sequence, Collection
        >>> checks.isiterabletype(Sequence[str])
        True
        >>> checks.isiterabletype(Collection)
        True
        >>> checks.isiterabletype(str)
        True
        >>> checks.isiterabletype(tuple)
        True
        >>> checks.isiterabletype(int)
        False
    """
    obj = inspection.origin(obj)
    return builtins.issubclass(obj, Iterable)


@lru_cache(maxsize=None)
def isiteratortype(obj: type[ObjectT]) -> TypeGuard[type[Iterator]]:
    """Check whether the given object is a subclass of an Iterator.

    Examples:
        >>> from typical import checks
        >>> def mygen(): yield 1
        ...
        >>> checks.isiteratortype(mygen().__class__)
        True
        >>> checks.isiteratortype(iter([]).__class__)
        True
        >>> checks.isiteratortype(mygen)
        False
        >>> checks.isiteratortype(list)
        False
    """
    obj = inspection.origin(obj)
    return builtins.issubclass(obj, Iterator)


@lru_cache(maxsize=None)
def istupletype(obj: type[Any]) -> TypeGuard[type[tuple]]:
    """Tests whether the given type is a subclass of :py:class:`tuple`.

    Examples:
        >>> from typical import checks
        >>> from typing import NamedTuple, Tuple
        >>> class MyTup(NamedTuple):
        ...     field: int
        ...
        >>> checks.istupletype(tuple)
        True
        >>> checks.istupletype(Tuple[str])
        True
        >>> checks.istupletype(MyTup)
        True
    """
    obj = inspection.origin(obj)
    return obj is tuple or issubclass(obj, tuple)


@lru_cache(maxsize=None)
def iscollectiontype(obj: type[ObjectT]) -> TypeGuard[type[Collection]]:
    """Test whether this annotation is a subclass of :py:class:`typing.Collection`.

    Includes builtins.

    Examples:
        >>> from typical import checks
        >>> from typing import Collection, Mapping, NewType
        >>> checks.iscollectiontype(Collection)
        True
        >>> checks.iscollectiontype(Mapping[str, str])
        True
        >>> checks.iscollectiontype(str)
        True
        >>> checks.iscollectiontype(list)
        True
        >>> checks.iscollectiontype(NewType("Foo", dict))
        True
        >>> checks.iscollectiontype(int)
    False
    """
    obj = inspection.origin(obj)
    return obj in _COLLECTIONS or builtins.issubclass(obj, Collection)


@lru_cache(maxsize=None)
def ismappingtype(obj: type[ObjectT]) -> TypeGuard[type[Mapping]]:
    """Test whether this annotation is a subtype of :py:class:`typing.Mapping`.

    Examples:
        >>> from typical import checks
        >>> from typing import Mapping, Dict, DefaultDict, NewType
        >>> checks.ismappingtype(Mapping)
        True
        >>> checks.ismappingtype(Dict[str, str])
        True
        >>> checks.ismappingtype(DefaultDict)
        True
        >>> checks.ismappingtype(dict)
        True
        >>> class MyDict(dict): ...
        ...
        >>> checks.ismappingtype(MyDict)
        True
        >>> class MyMapping(Mapping): ...
        ...
        >>> checks.ismappingtype(MyMapping)
        True
        >>> checks.ismappingtype(NewType("Foo", dict))
        True
    """
    obj = inspection.origin(obj)
    return builtins.issubclass(
        obj, (dict, Record, sqlite3.Row, types.MappingProxyType)
    ) or builtins.issubclass(obj, Mapping)


@lru_cache(maxsize=None)
def isenumtype(obj: type[ObjectT]) -> TypeGuard[type[enum.Enum]]:
    """Test whether this annotation is a subclass of :py:class:`enum.Enum`

    Examples:
        >>> from typical import checks
        >>> import enum
        >>>
        >>> class FooNum(enum.Enum): ...
        ...
        >>> checks.isenumtype(FooNum)
        True
    """
    return issubclass(obj, enum.Enum)


@lru_cache(maxsize=None)
def isclassvartype(obj: type) -> bool:
    """Test whether an annotation is a ClassVar annotation.

    Examples:
        >>> from typical import checks
        >>> from typing import ClassVar, NewType
        >>> checks.isclassvartype(ClassVar[str])
        True
        >>> checks.isclassvartype(NewType("Foo", ClassVar[str]))
        True
    """
    obj = inspection.resolve_supertype(obj)
    return getattr(obj, "__origin__", obj) is ClassVar


_UNWRAPPABLE = (
    isclassvartype,
    isoptionaltype,
    isreadonly,
    iswriteonly,
    isfinal,
    isstrict,
)


@lru_cache(maxsize=None)
def should_unwrap(obj: type[ObjectT]) -> bool:
    """Test whether we should use the __args__ attr for resolving the type.

    This is useful for determining what type to use at run-time for coercion.
    """
    return (not isliteral(obj)) and any(x(obj) for x in _UNWRAPPABLE)


@lru_cache(maxsize=None)
def isfromdictclass(obj: type[ObjectT]) -> TypeGuard[_FromDict]:
    """Test whether this annotation is a class with a `from_dict()` method."""
    return inspect.isclass(obj) and hasattr(obj, "from_dict")


class _FromDict(Protocol):
    def from_dict(self, *args, **kwargs) -> _FromDict:
        ...


@lru_cache(maxsize=None)
def isfrozendataclass(obj: type[ObjectT]) -> TypeGuard[_FrozenDataclass]:
    """Test whether this is a dataclass and whether it's frozen."""
    return getattr(getattr(obj, "__dataclass_params__", None), "frozen", False)


class _FrozenDataclass(Protocol):
    __dataclass_params__: dataclasses._DataclassParams  # type: ignore


_isinstance = isinstance


@lru_cache(maxsize=None)
def _type_check(t) -> bool:
    if _isinstance(t, tuple):
        return all(_type_check(x) for x in t)
    return inspect.isclass(t)


def isinstance(o: Any, t: Union[type, Tuple[type, ...]]) -> bool:
    """An instance check which returns `False` if `t` is an instance rather than a type.

    Examples:
        >>> from typical import checks
        >>> checks.isinstance("", str)
        True
        >>> checks.isinstance("", "")
        False
    """
    return _type_check(t) and builtins.isinstance(o, t)


def issubclass(o: Any, t: Union[type, Tuple[type, ...]]) -> bool:
    """A subclass check which returns `False` if `t` or `o` are instances.

    Notes:
        Not compatible with classes from :py:mod:`typing`, as they return False with
        :py:func:`inspect.isclass`

    Examples:
        >>> from typical import checks
        >>> class MyStr(str): ...
        ...
        >>> checks.issubclass(MyStr, str)
        True
        >>> checks.issubclass(MyStr(), str)
        False
        >>> checks.issubclass(MyStr, str())
    False
    """
    return _type_check(t) and _type_check(o) and builtins.issubclass(o, t)


@lru_cache(maxsize=None)
def isconstrained(obj: type[ObjectT]) -> TypeGuard[_Constrained]:
    """Test whether a type is restricted.

    Examples:
        >>> import typical
        >>> from typical import checks
        >>> from typing import NewType
        >>>
        >>> @typical.constrained(min=0, max=1, inclusive_min=True, inclusive_max=True)
        ... class TinyInt(int): ...
        ...
        >>> checks.isconstrained(TinyInt)
        True
        >>> Switch = NewType("Switch", TinyInt)
        >>> checks.isconstrained(Switch)
        True
    """
    return hasattr(inspection.resolve_supertype(obj), "__constraints__")


class _Constrained(Protocol):
    __constraints__: AbstractConstraintValidator


__hashgetter = attrgetter("__hash__")


def ishashable(obj: ObjectT) -> TypeGuard[Hashable]:
    """Check whether an object is hashable.

    An order of magnitude faster than :py:class:`isinstance` with
    :py:class:`typing.Hashable`

    Examples:
        >>> from typical import checks
        >>> checks.ishashable(str())
        True
        >>> checks.ishashable(frozenset())
        True
        >>> checks.ishashable(list())
        False
    """
    return __hashgetter(obj) is not None


@lru_cache(maxsize=None)
def istypeddict(obj: Any) -> bool:
    """Check whether an object is a :py:class:`typing.TypedDict`.

    Examples:
        >>> from typical import checks
        >>> from typical.compat import TypedDict
        >>>
        >>> class FooMap(TypedDict):
        ...     bar: str
        ...
        >>> checks.istypeddict(FooMap)
        True
    """
    return (
        inspect.isclass(obj)
        and dict in {*inspect.getmro(obj)}
        and hasattr(obj, "__total__")
    )


@lru_cache(maxsize=None)
def istypedtuple(obj: type[ObjectT]) -> TypeGuard[type[NamedTuple]]:
    """Check whether an object is a "typed" tuple (:py:class:`typing.NamedTuple`).

    Examples:
        >>> from typical import checks
        >>> from typing import NamedTuple
        >>>
        >>> class FooTup(NamedTuple):
        ...     bar: str
        ...
        >>> checks.istypedtuple(FooTup)
        True
    """
    return (
        inspect.isclass(obj)
        and issubclass(obj, tuple)
        and hasattr(obj, "__annotations__")
    )


@lru_cache(maxsize=None)
def isnamedtuple(obj: type[ObjectT]) -> TypeGuard[NamedTuple]:
    """Check whether an object is a "named" tuple (:py:func:`collections.namedtuple`).

    Examples:
        >>> from typical import checks
        >>> from collections import namedtuple
        >>>
        >>> FooTup = namedtuple("FooTup", ["bar"])
        >>> checks.isnamedtuple(FooTup)
        True
    """
    return inspect.isclass(obj) and issubclass(obj, tuple) and hasattr(obj, "_fields")


@lru_cache(maxsize=None)
def isfixedtuple(obj: type[ObjectT]) -> TypeGuard[tuple]:
    """Check whether an object is a "fixed" tuple, e.g., tuple[int, int].

    Examples:
        >>> from typical import checks
        >>> from typing import Tuple
        >>>
        >>>
        >>> checks.isfixedtuple(Tuple[str, int])
        True
        >>> checks.isfixedtuple(Tuple[str, ...])
        False
    """
    args = inspection.get_args(obj)
    origin = inspection.get_origin(obj)
    if not args or args[-1] is ...:
        return False
    return issubclass(origin, tuple)


def isforwardref(obj: Any) -> TypeGuard[ForwardRef]:
    """Tests whether the given object is a :py:class:`typing.ForwardRef`."""
    return obj.__class__ is ForwardRef


def isproperty(obj) -> TypeGuard[types.DynamicClassAttribute]:
    """Test whether the given object is an instance of :py:class:`property` or :py:class:`functools.cached_property.

    Examples:
        >>> import functools
        >>> from typical import checks
        >>> class Foo:
        ...     @property
        ...     def prop(self) -> int:
        ...         return 1
        ...
        ...     @functools.cached_property
        ...     def cached(self) -> str:
        ...         return "foo"
        ...
        >>> checks.isproperty(Foo.prop)
        True
        >>> checks.isproperty(Foo.cached)
        True
    """

    return builtins.issubclass(obj.__class__, (property, functools.cached_property))


def isdescriptor(obj) -> TypeGuard[DescriptorT]:
    """Test whether the given object is a :py:class:`types.GetSetDescriptorType`

    Examples:
        >>> from typical import checks
        >>> class StringDescriptor:
        ...     __slots__ = ("value",)
        ...
        ...     def __init__(self, default: str = "value"):
        ...         self.value = default
        ...
        ...     def __get__(self, instance: Any, value: str) -> str:
        ...         return self.value
        ...
        >>> checks.isdescriptor(StringDescriptor)
        True
    """
    return {*dir(obj)} & _DESCRIPTOR_METHODS <= _DESCRIPTOR_METHODS


_DESCRIPTOR_METHODS = frozenset(("__get__", "__set__", "__delete__", "__set_name__"))


_VT_in = TypeVar("_VT_in")
_VT_co = TypeVar("_VT_co", covariant=True)
_VT_cont = TypeVar("_VT_cont", contravariant=True)


class GetDescriptor(Protocol[_VT_co]):
    @overload
    def __get__(self, instance: None, owner: Any) -> GetDescriptor:
        ...

    @overload
    def __get__(self, instance: object, owner: Any) -> _VT_co:
        ...

    def __get__(self, instance: Any, owner: Any) -> GetDescriptor | _VT_co:
        ...


class SetDescriptor(Protocol[_VT_cont]):
    def __set__(self, instance: Any, value: _VT_cont):
        ...


class DeleteDescriptor(Protocol[_VT_co]):
    def __delete__(self, instance: Any):
        ...


class SetNameDescriptor(Protocol):
    def __set_name__(self, owner: Any, name: str):
        ...


DescriptorT = Union[GetDescriptor, SetDescriptor, DeleteDescriptor, SetNameDescriptor]


def issimpleattribute(v) -> bool:
    """Test whether the given object is a static value

    (e.g., not a function, class, or descriptor).

    Examples:
        >>> from typical import checks
        >>> class MyOperator:
        ...     type = str
        ...
        ...     def operate(self, v) -> type:
        ...         return self.type(v)
        ...
        ...     @property
        ...     def default(self) -> type:
        ...         return self.type()
        ...
        >>> checks.issimpleattribute(MyOperator.type)
        False
        >>> checks.issimpleattribute(MyOperator.operate)
        False
        >>> checks.issimpleattribute(MyOperator.default)
        False
    """
    return not any(c(v) for c in _ATTR_CHECKS)


_ATTR_CHECKS = (inspect.isclass, inspect.isroutine, isproperty)


def isabstract(o) -> TypeGuard[abc.ABC]:
    """Test whether the given object is an abstract type.

    Examples:
        >>> import abc
        >>> import numbers
        >>> from typical import checks
        >>>
        >>> checks.isabstract(numbers.Number)
        True
        >>>
        >>> class MyABC(abc.ABC): ...
        ...
        >>> checks.isabstract(MyABC)
        True

    """
    return inspect.isabstract(o) or o in _ABCS


# Custom list of ABCs which incorrectly evaluate to false
_ABCS = frozenset({numbers.Number})


def istypicklass(obj) -> TypeGuard[TypicObjectT]:
    return hasattr(obj, "__typic_fields__")


@lru_cache(maxsize=None)
def istexttype(t: type[Any]) -> TypeGuard[type[str | bytes | bytearray]]:
    """Test whether the given type is a subclass of text or bytes.

    Examples:
        >>> from typical import checks
        >>> class MyStr(str): ...
        ...
        >>> checks.istexttype(MyStr)
        True
    """
    return issubclass(t, (str, bytes, bytearray))


@lru_cache(maxsize=None)
def isnumbertype(t: type[Any]) -> TypeGuard[type[numbers.Number]]:
    """Test whether `t` is a subclass of the :py:class:`numbers.Number` protocol.

    Examples:
        >>> import decimal
        >>> from typical import checks
        >>> checks.isnumbertype(int)
        True
        >>> checks.isnumbertype(float)
        True
        >>> checks.isnumbertype(decimal.Decimal)
        True
    """
    return issubclass(t, numbers.Number)


@lru_cache(maxsize=None)
def isstructuredtype(t: type[Any]) -> bool:
    """Test whether the given type has a fixed set of fields.

    Examples:
        >>> import dataclasses
        >>> from typing import Tuple, NamedTuple, TypedDict, Union, Literal, Collection
        >>> from typical import checks
        >>>
        >>> checks.isstructuredtype(Tuple[str, int])
        True
        >>> checks.isstructuredtype(class MyDict(TypedDict): ...)
        True
        >>> checks.isstructuredtype(class MyTup(NamedTuple): ...)
        True
        >>> checks.isstructuredtype(class MyClass: ...)
        True
        >>> checks.isstructuredtype(Union[str, int])
        False
        >>> checks.isstructuredtype(Literal[1, 2])
        False
        >>> checks.isstructuredtype(tuple)
        False
        >>> checks.isstructuredtype(Collection[str])
        False
    """
    return (
        isfixedtuple(t)
        or isnamedtuple(t)
        or istypeddict(t)
        or (not isstdlibsubtype(t) and not isuniontype(t) and not isliteral(t))
    )


@lru_cache(maxsize=None)
def isgeneric(t: Any) -> bool:
    """Test whether the given type is a typing generic.

    Examples:
        >>> from typing import Tuple, Generic, TypeVar
        >>> from typical import checks
        >>>
        >>> checks.isgeneric(Tuple)
        True
        >>> checks.isgeneric(tuple)
        False
        >>> T = TypeVar("T")
        >>> class MyGeneric(Generic[T]): ...
        >>> checks.isgeneric(MyGeneric[int])
        True
    """
    strobj = str(t)
    is_generic = (
        strobj.startswith("typing.")
        or strobj.startswith("typing_extensions.")
        or "[" in strobj
        or issubclass(t, Generic)  # type: ignore[arg-type]
    )
    return is_generic
