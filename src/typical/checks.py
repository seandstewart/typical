from __future__ import annotations

import abc
import builtins
import collections
import dataclasses
import datetime
import decimal
import enum
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
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
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
>>> from typing import Type
>>> def get_type(obj: typic.ObjectT) -> Type[ObjectT]:
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
    uuid.SafeUUID,
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
    obj: Type[ObjectT] | types.FunctionType,
) -> TypeGuard[Type[BuiltInTypeT]]:
    """Check whether the provided object is a builtin-type.

    Python stdlib and Python documentation have no "definitive list" of
    builtin-**types**, despite the fact that they are well-known. The closest we have
    is https://docs.python.org/3.7/library/functions.html, which clumps the
    builtin-types with builtin-functions. Despite clumping these types with functions
    in the documentation, these types eval as False when compared to
    :py:class:`types.BuiltinFunctionType`, which is meant to be an alias for the
    builtin-functions listed in the documentation.

    All this to say, here we are with a custom check to determine whether a type is a
    builtin.

    Parameters
    ----------
    obj

    Examples
    --------

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
def isstdlibtype(obj: Type[ObjectT]) -> TypeGuard[Type[STDLibTypeT]]:
    return (
        inspection.resolve_supertype(obj) in STDLIB_TYPES
        or inspection.resolve_supertype(type(obj)) in STDLIB_TYPES
    )


@lru_cache(maxsize=None)
def isbuiltinsubtype(t: Type[ObjectT]) -> TypeGuard[Type[BuiltInTypeT]]:
    """Check whether the provided type is a subclass of a builtin-type.

    Parameters
    ----------
    t

    Examples
    --------
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
def isstdlibsubtype(t: Type[ObjectT]) -> TypeGuard[Type[STDLibTypeT]]:
    return issubclass(inspection.resolve_supertype(t), STDLIB_TYPES_TUPLE)


def isbuiltininstance(o: ObjectT) -> TypeGuard[BuiltInTypeT]:
    return _isinstance(o, BUILTIN_TYPES_TUPLE)


def isstdlibinstance(o: ObjectT) -> TypeGuard[STDLibTypeT]:
    return _isinstance(o, STDLIB_TYPES_TUPLE)


@lru_cache(maxsize=None)
def isoptionaltype(obj: Type[ObjectT]) -> TypeGuard[Optional[ObjectT]]:
    """Test whether an annotation is :py:class`typing.Optional`, or can be treated as.

    :py:class:`typing.Optional` is an alias for `typing.Union[<T>, None]`, so both are
    "optional".

    Parameters
    ----------
    obj

    Examples
    --------

    >>> from typical import checks
    >>> from typing import Optional, Union, Dict
    >>> checks.isoptionaltype(Optional[str])
    True
    >>> checks.isoptionaltype(Union[str, None])
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
def isuniontype(obj: Type[ObjectT]) -> TypeGuard[Union]:
    return inspection.get_name(inspection.origin(obj)) in ("Union", "UnionType")


@lru_cache(maxsize=None)
def isreadonly(obj: Type[ObjectT]) -> TypeGuard[ReadOnly]:
    """Test whether an annotation is marked as :py:class:`typic.ReadOnly`

    Parameters
    ----------
    obj

    Examples
    --------

    >>> from typical import checks
    >>> from typing import NewType
    >>> checks.isreadonly(typical.ReadOnly[str])
    True
    >>> checks.isreadonly(NewType("Foo", typical.ReadOnly[str]))
    True
    """
    return inspection.origin(obj) in (ReadOnly, Final) or isclassvartype(obj)


@lru_cache(maxsize=None)
def isfinal(obj: Type[ObjectT]) -> bool:
    """Test whether an annotation is :py:class:`typing.Final`.

    Examples
    --------

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
    return inspection.origin(obj) is Literal or (
        obj.__class__ is ForwardRef and obj.__forward_arg__.startswith("Literal")
    )


@lru_cache(maxsize=None)
def iswriteonly(obj: Type[ObjectT]) -> TypeGuard[WriteOnly]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> from typical import checks
    >>> from typing import NewType
    >>> checks.iswriteonly(typical.WriteOnly[str])
    True
    >>> checks.iswriteonly(NewType("Foo", typical.WriteOnly[str]))
    True
    """
    return inspection.origin(obj) is WriteOnly


@lru_cache(maxsize=None)
def isstrict(obj: Type[ObjectT]) -> TypeGuard[strict.Strict]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> from typical import checks
    >>> from typing import NewType
    >>> checks.isstrict(typical.Strict[str])
    True
    >>> checks.isstrict(NewType("Foo", typical.Strict[str]))
    True
    """
    return inspection.origin(obj) is strict.Strict


@lru_cache(maxsize=None)
def isdatetype(
    obj: Type[ObjectT],
) -> TypeGuard[Type[Union[datetime.datetime, datetime.date]]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

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
    obj: Type[ObjectT],
) -> TypeGuard[Type[Union[datetime.datetime, datetime.date]]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

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
def istimetype(obj: Type[ObjectT]) -> TypeGuard[Type[datetime.time]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

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
def istimedeltatype(obj: Type[ObjectT]) -> TypeGuard[Type[datetime.timedelta]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

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
def isdecimaltype(obj: Type[ObjectT]) -> TypeGuard[Type[decimal.Decimal]]:
    """Test whether this annotation is a Decimal object.

    Parameters
    ----------
    obj

    Examples
    --------

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
def isuuidtype(obj: Type[ObjectT]) -> TypeGuard[Type[uuid.UUID]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

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
def isiterabletype(obj: Type[ObjectT]) -> TypeGuard[Type[Iterable]]:
    obj = inspection.origin(obj)
    return builtins.issubclass(obj, Iterable)


@lru_cache(maxsize=None)
def isiteratortype(obj: Type[ObjectT]) -> TypeGuard[Type[Iterator]]:
    obj = inspection.origin(obj)
    return builtins.issubclass(obj, Iterator)


@lru_cache(maxsize=None)
def istupletype(obj: Any) -> TypeGuard[Type[tuple]]:
    obj = inspection.origin(obj)
    return obj is tuple or issubclass(obj, tuple)


@lru_cache(maxsize=None)
def iscollectiontype(obj: Type[ObjectT]) -> TypeGuard[Type[Collection]]:
    """Test whether this annotation is a subclass of :py:class:`typing.Collection`.

    Includes builtins.

    Parameters
    ----------
    obj

    Examples
    --------

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
def ismappingtype(obj: Type[ObjectT]) -> TypeGuard[Type[Mapping]]:
    """Test whether this annotation is a subtype of :py:class:`typing.Mapping`.

    Parameters
    ----------
    obj

    Examples
    --------

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
def isenumtype(obj: Type[ObjectT]) -> TypeGuard[Type[enum.Enum]]:
    """Test whether this annotation is a subclass of :py:class:`enum.Enum`

    Parameters
    ----------
    obj

    Examples
    --------

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
def isclassvartype(obj: Type) -> bool:
    """Test whether an annotation is a ClassVar annotation.

    Examples
    --------
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
def should_unwrap(obj: Type[ObjectT]) -> bool:
    """Test whether we should use the __args__ attr for resolving the type.

    This is useful for determining what type to use at run-time for coercion.
    """
    return (not isliteral(obj)) and any(x(obj) for x in _UNWRAPPABLE)


@lru_cache(maxsize=None)
def isfromdictclass(obj: Type[ObjectT]) -> TypeGuard[_FromDict]:
    """Test whether this annotation is a class with a `from_dict()` method."""
    return inspect.isclass(obj) and hasattr(obj, "from_dict")


class _FromDict(Protocol):
    def from_dict(self, *args, **kwargs) -> _FromDict:
        ...


@lru_cache(maxsize=None)
def isfrozendataclass(obj: Type[ObjectT]) -> TypeGuard[_FrozenDataclass]:
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


def isinstance(o: Any, t: Union[Type, Tuple[Type, ...]]) -> bool:
    """A safer instance check...

    Validates that `t` is not an instance.

    Parameters
    ----------
    o
        The object to test.
    t
        The type(s) to test against.

    Examples
    --------
    >>> from typical import checks
    >>> checks.isinstance("", str)
    True
    >>> checks.isinstance("", "")
    False
    """
    return _type_check(t) and builtins.isinstance(o, t)


def issubclass(o: Any, t: Union[Type, Tuple[Type, ...]]) -> bool:
    """A safer subclass check...

    Validates that `t` and/or `o` are not instances.

    Parameters
    ----------
    o
        The type to validate
    t
        The type(s) to validate against

    Notes
    -----
    Not compatible with classes from :py:mod:`typing`, as they return False with
    :py:func:`inspect.isclass`

    Examples
    --------
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
def isconstrained(obj: Type[ObjectT]) -> TypeGuard[_Constrained]:
    """Test whether a type is restricted.

    Parameters
    ----------
    obj

    Examples
    --------
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

    Parameters
    ----------
    obj

    Examples
    --------
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

    Parameters
    ----------
    obj

    Examples
    --------
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
def istypedtuple(obj: Type[ObjectT]) -> TypeGuard[Type[NamedTuple]]:
    """Check whether an object is a "typed" tuple (:py:class:`typing.NamedTuple`).

    Parameters
    ----------
    obj

    Examples
    --------
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
def isnamedtuple(obj: Type[ObjectT]) -> TypeGuard[NamedTuple]:
    """Check whether an object is a "named" tuple (:py:func:`collections.namedtuple`).

    Parameters
    ----------
    obj

    Examples
    --------
    >>> from typical import checks
    >>> from collections import namedtuple
    >>>
    >>> FooTup = namedtuple("FooTup", ["bar"])
    >>> checks.isnamedtuple(FooTup)
    True
    """
    return inspect.isclass(obj) and issubclass(obj, tuple) and hasattr(obj, "_fields")


@lru_cache(maxsize=None)
def isfixedtuple(obj: Type[ObjectT]) -> TypeGuard[tuple]:
    """Check whether an object is a "fixed" tuple, e.g., tuple[int, int].

    Parameters
    ----------
    obj

    Examples
    --------
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
    return obj.__class__ is ForwardRef


def isproperty(obj) -> TypeGuard[types.GetSetDescriptorType]:
    return obj.__class__.__name__ in {"property", "cached_property"}


def isdescriptor(obj) -> TypeGuard[types.GetSetDescriptorType]:
    return (
        hasattr(obj, "__get__")
        or hasattr(obj, "__set__")
        or hasattr(obj, "__set_name__")
    )


def issimpleattribute(v) -> bool:
    return not any(c(v) for c in _ATTR_CHECKS)


_ATTR_CHECKS = (inspect.isclass, inspect.isroutine, isproperty)


def isabstract(o) -> TypeGuard[abc.ABC]:
    return inspect.isabstract(o) or o in _ABCS


# Custom list of ABCs which incorrectly evaluate to false
_ABCS = frozenset({numbers.Number})


def istypicklass(obj) -> TypeGuard[TypicObjectT]:
    return hasattr(obj, "__typic_fields__")


@lru_cache(maxsize=None)
def istexttype(t: Type[Any]) -> TypeGuard[Type[str | bytes | bytearray]]:
    return issubclass(t, (str, bytes, bytearray))


@lru_cache(maxsize=None)
def isnumbertype(t: Type[Any]) -> TypeGuard[Type[numbers.Number]]:
    return issubclass(t, numbers.Number)


@lru_cache(maxsize=None)
def isstructuredtype(t: Type[Any]) -> bool:
    return (
        isfixedtuple(t)
        or isnamedtuple(t)
        or istypeddict(t)
        or (not isstdlibsubtype(t) and not isuniontype(t) and not isliteral(t))
    )


@lru_cache(maxsize=None)
def isgeneric(t: Any) -> bool:
    strobj = str(t)
    is_generic = (
        strobj.startswith("typing.")
        or strobj.startswith("typing_extensions.")
        or "[" in strobj
    )
    return is_generic
