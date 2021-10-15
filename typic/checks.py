from __future__ import annotations

import abc
import builtins
import dataclasses
import datetime
import decimal
import enum
import inspect
import ipaddress
import numbers
import pathlib
import types
import uuid
from collections import namedtuple
from operator import attrgetter
from typing import (
    Any,
    Optional,
    Union,
    Collection,
    Mapping,
    ClassVar,
    Type,
    Tuple,
    TypeVar,
    Iterable,
    Iterator,
    Hashable,
    NamedTuple,
    TYPE_CHECKING,
)

import typic
import typic.common
import typic.util as util
import typic.strict as strict

from typic.compat import (
    Final,
    ForwardRef,
    Literal,
    lru_cache,
    TypeGuard,
    TypedDict,
    Protocol,
    Record,
)

if TYPE_CHECKING:
    from typic.api import TypicObjectT

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
    "isdescriptor",
    "isenumtype",
    "isfinal",
    "isforwardref",
    "isfromdictclass",
    "isfrozendataclass",
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
]
STDLIB_TYPES = frozenset(
    (type(None), *(t for t in STDLibTypeT.__args__ if t is not None))  # type: ignore
)
STDLIB_TYPES_TUPLE = tuple(STDLIB_TYPES)


@lru_cache(maxsize=None)
def isbuiltintype(obj: Type[ObjectT]) -> TypeGuard[Type[BuiltInTypeT]]:
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

    >>> import typic
    >>> from typing import NewType, Mapping
    >>> typic.isbuiltintype(str)
    True
    >>> typic.isbuiltintype(NewType("MyStr", str))
    True
    >>> class Foo: ...
    ...
    >>> typic.isbuiltintype(Foo)
    False
    >>> typic.isbuiltintype(Mapping)
    False
    """
    return (
        util.resolve_supertype(obj) in BUILTIN_TYPES
        or util.resolve_supertype(type(obj)) in BUILTIN_TYPES
    )


@lru_cache(maxsize=None)
def isstdlibtype(obj: Type[ObjectT]) -> TypeGuard[Type[STDLibTypeT]]:
    return (
        util.resolve_supertype(obj) in STDLIB_TYPES
        or util.resolve_supertype(type(obj)) in STDLIB_TYPES
    )


@lru_cache(maxsize=None)
def isbuiltinsubtype(t: Type[ObjectT]) -> TypeGuard[Type[BuiltInTypeT]]:
    """Check whether the provided type is a subclass of a builtin-type.

    Parameters
    ----------
    t

    Examples
    --------
    >>> import typic
    >>> from typing import NewType, Mapping
    >>> class SuperStr(str): ...
    ...
    >>> typic.isbuiltinsubtype(SuperStr)
    True
    >>> typic.isbuiltinsubtype(NewType("MyStr", SuperStr))
    True
    >>> class Foo: ...
    ...
    >>> typic.isbuiltintype(Foo)
    False
    >>> typic.isbuiltintype(Mapping)
    False
    """
    return issubclass(util.resolve_supertype(t), BUILTIN_TYPES_TUPLE)


@lru_cache(maxsize=None)
def isstdlibsubtype(t: Type[ObjectT]) -> TypeGuard[Type[STDLibTypeT]]:
    return issubclass(util.resolve_supertype(t), STDLIB_TYPES_TUPLE)


def isbuiltininstance(o: ObjectT) -> TypeGuard[BuiltInTypeT]:
    return _isinstance(o, BUILTIN_TYPES_TUPLE)


def isstdlibinstance(o: ObjectT) -> TypeGuard[STDLibTypeT]:
    return _isinstance(o, STDLIB_TYPES_TUPLE)


@lru_cache(maxsize=None)
def isoptionaltype(obj: Type[ObjectT]) -> TypeGuard[Optional]:
    """Test whether an annotation is :py:class`typing.Optional`, or can be treated as.

    :py:class:`typing.Optional` is an alias for `typing.Union[<T>, None]`, so both are
    "optional".

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> from typing import Optional, Union, Dict
    >>> typic.isoptionaltype(Optional[str])
    True
    >>> typic.isoptionaltype(Union[str, None])
    True
    >>> typic.isoptionaltype(Dict[str, None])
    False
    """
    args = getattr(obj, "__args__", ())
    return (
        len(args) > 1
        and args[-1]
        in {
            type(None),
            None,
        }  # noqa: E721 - we don't know what args[-1] is, so this is safer
        and util.get_name(util.origin(obj)) in {"Optional", "Union", "Literal"}
    )


@lru_cache(maxsize=None)
def isuniontype(obj: Type[ObjectT]) -> TypeGuard[Union]:
    return util.get_name(util.origin(obj)) in {"Union", "UnionType"}


@lru_cache(maxsize=None)
def isreadonly(obj: Type[ObjectT]) -> TypeGuard[typic.common.ReadOnly]:
    """Test whether an annotation is marked as :py:class:`typic.ReadOnly`

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> from typing import NewType
    >>> typic.isreadonly(typic.ReadOnly[str])
    True
    >>> typic.isreadonly(NewType("Foo", typic.ReadOnly[str]))
    True
    """
    return util.origin(obj) is typic.common.ReadOnly


@lru_cache(maxsize=None)
def isfinal(obj: Type[ObjectT]) -> bool:
    """Test whether an annotation is :py:class:`typing.Final`.

    Examples
    --------

    >>> import typic
    >>> from typing import NewType
    >>> from typic.compat import Final
    >>> typic.isfinal(Final[str])
    True
    >>> typic.isfinal(NewType("Foo", Final[str]))
    True
    """
    return util.origin(obj) is Final


@lru_cache(maxsize=None)
def isliteral(obj: Type) -> TypeGuard[Literal]:
    return util.origin(obj) is Literal or (
        obj.__class__ is ForwardRef and obj.__forward_arg__.startswith("Literal")
    )


@lru_cache(maxsize=None)
def iswriteonly(obj: Type[ObjectT]) -> TypeGuard[typic.common.WriteOnly]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> from typing import NewType
    >>> typic.iswriteonly(typic.WriteOnly[str])
    True
    >>> typic.iswriteonly(NewType("Foo", typic.WriteOnly[str]))
    True
    """
    return util.origin(obj) is typic.common.WriteOnly


@lru_cache(maxsize=None)
def isstrict(obj: Type[ObjectT]) -> TypeGuard[typic.Strict]:
    """Test whether an annotation is marked as :py:class:`typic.WriteOnly`.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> from typing import NewType
    >>> typic.isstrict(typic.Strict[str])
    True
    >>> typic.isstrict(NewType("Foo", typic.Strict[str]))
    True
    """
    return util.origin(obj) is strict.Strict


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

    >>> import typic
    >>> import datetime
    >>> from typing import NewType
    >>> typic.isdatetype(datetime.datetime)
    True
    >>> typic.isdatetype(datetime.date)
    True
    >>> typic.isdatetype(NewType("Foo", datetime.datetime))
    True
    """
    return builtins.issubclass(util.origin(obj), (datetime.datetime, datetime.date))


@lru_cache(maxsize=None)
def istimetype(obj: Type[ObjectT]) -> TypeGuard[Type[datetime.time]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> import datetime
    >>> from typing import NewType
    >>> typic.istimetype(datetime.time)
    True
    >>> typic.istimetype(NewType("Foo", datetime.time))
    True
    """
    return builtins.issubclass(util.origin(obj), datetime.time)


@lru_cache(maxsize=None)
def istimedeltatype(obj: Type[ObjectT]) -> TypeGuard[Type[datetime.timedelta]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> import datetime
    >>> from typing import NewType
    >>> typic.istimedeltatype(datetime.timedelta)
    True
    >>> typic.istimedeltatype(NewType("Foo", datetime.timedelta))
    True
    """
    return builtins.issubclass(util.origin(obj), datetime.timedelta)


@lru_cache(maxsize=None)
def isuuidtype(obj: Type[ObjectT]) -> TypeGuard[Type[uuid.UUID]]:
    """Test whether this annotation is a a date/datetime object.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> import uuid
    >>> from typing import NewType
    >>> typic.isuuidtype(uuid.UUID)
    True
    >>> class MyUUID(uuid.UUID): ...
    ...
    >>> typic.isuuidtype(MyUUID)
    True
    >>> typic.isuuidtype(NewType("Foo", uuid.UUID))
    True
    """
    return builtins.issubclass(util.origin(obj), uuid.UUID)


_COLLECTIONS = {list, set, tuple, frozenset, dict, str, bytes}


@lru_cache(maxsize=None)
def isiterabletype(obj: Type[ObjectT]) -> TypeGuard[Type[Iterable]]:
    obj = util.origin(obj)
    return builtins.issubclass(obj, Iterable)


@lru_cache(maxsize=None)
def isiteratortype(obj: Type[ObjectT]) -> TypeGuard[Type[Iterator]]:
    obj = util.origin(obj)
    return builtins.issubclass(obj, Iterator)


@lru_cache(maxsize=None)
def istupletype(obj: Type[ObjectT]) -> TypeGuard[Type[tuple]]:
    obj = util.origin(obj)
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

    >>> import typic
    >>> from typing import Collection, Mapping, NewType
    >>> typic.iscollectiontype(Collection)
    True
    >>> typic.iscollectiontype(Mapping[str, str])
    True
    >>> typic.iscollectiontype(str)
    True
    >>> typic.iscollectiontype(list)
    True
    >>> typic.iscollectiontype(NewType("Foo", dict))
    True
    >>> typic.iscollectiontype(int)
    False
    """
    obj = util.origin(obj)
    return obj in _COLLECTIONS or builtins.issubclass(obj, Collection)


@lru_cache(maxsize=None)
def ismappingtype(obj: Type[ObjectT]) -> TypeGuard[Type[Mapping]]:
    """Test whether this annotation is a subtype of :py:class:`typing.Mapping`.

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> from typing import Mapping, Dict, DefaultDict, NewType
    >>> typic.ismappingtype(Mapping)
    True
    >>> typic.ismappingtype(Dict[str, str])
    True
    >>> typic.ismappingtype(DefaultDict)
    True
    >>> typic.ismappingtype(dict)
    True
    >>> class MyDict(dict): ...
    ...
    >>> typic.ismappingtype(MyDict)
    True
    >>> class MyMapping(Mapping): ...
    ...
    >>> typic.ismappingtype(MyMapping)
    True
    >>> typic.ismappingtype(NewType("Foo", dict))
    True
    """
    obj = util.origin(obj)
    return (
        builtins.issubclass(obj, dict)
        or builtins.issubclass(obj, Mapping)
        or builtins.issubclass(obj, Record)
    )


@lru_cache(maxsize=None)
def isenumtype(obj: Type[ObjectT]) -> TypeGuard[Type[enum.Enum]]:
    """Test whether this annotation is a subclass of :py:class:`enum.Enum`

    Parameters
    ----------
    obj

    Examples
    --------

    >>> import typic
    >>> import enum
    >>>
    >>> class FooNum(enum.Enum): ...
    ...
    >>> typic.isenumtype(FooNum)
    True
    """
    return issubclass(obj, enum.Enum)


@lru_cache(maxsize=None)
def isclassvartype(obj: Type[ObjectT]) -> TypeGuard[ClassVar]:
    """Test whether an annotation is a ClassVar annotation.

    Examples
    --------
    >>> import typic
    >>> from typing import ClassVar, NewType
    >>> typic.isclassvartype(ClassVar[str])
    True
    >>> typic.isclassvartype(NewType("Foo", ClassVar[str]))
    True
    """
    obj = util.resolve_supertype(obj)
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
    >>> import typic
    >>> typic.isinstance("", str)
    True
    >>> typic.isinstance("", "")
    False
    """
    return _type_check(t) and builtins.isinstance(o, t)


def issubclass(o: Type[Any], t: Union[Type, Tuple[Type, ...]]) -> bool:
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
    >>> import typic
    >>> class MyStr(str): ...
    ...
    >>> typic.issubclass(MyStr, str)
    True
    >>> typic.issubclass(MyStr(), str)
    False
    >>> typic.issubclass(MyStr, str())
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
    >>> import typic
    >>> from typing import NewType
    >>>
    >>> @typic.constrained(ge=0, le=1)
    ... class TinyInt(int): ...
    ...
    >>> typic.isconstrained(TinyInt)
    True
    >>> Switch = NewType("Switch", TinyInt)
    >>> typic.isconstrained(Switch)
    True
    """
    return hasattr(util.resolve_supertype(obj), "__constraints__")


class _Constrained(Protocol):
    __constraints__: typic.ConstraintsProtocolT


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
    >>> import typic
    >>> typic.ishashable(str())
    True
    >>> typic.ishashable(frozenset())
    True
    >>> typic.ishashable(list())
    False
    """
    return __hashgetter(obj) is not None


@lru_cache(maxsize=None)
def istypeddict(obj: Type[ObjectT]) -> TypeGuard[Type[TypedDict]]:
    """Check whether an object is a :py:class:`typing.TypedDict`.

    Parameters
    ----------
    obj

    Examples
    --------
    >>> import typic
    >>> from typic.compat import TypedDict
    >>>
    >>> class FooMap(TypedDict):
    ...     bar: str
    ...
    >>> typic.istypeddict(FooMap)
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
    >>> import typic
    >>> from typing import NamedTuple
    >>>
    >>> class FooTup(NamedTuple):
    ...     bar: str
    ...
    >>> typic.istypedtuple(FooTup)
    True
    """
    return (
        inspect.isclass(obj)
        and issubclass(obj, tuple)
        and hasattr(obj, "__annotations__")
    )


@lru_cache(maxsize=None)
def isnamedtuple(obj: Type[ObjectT]) -> TypeGuard[namedtuple]:
    """Check whether an object is a "named" tuple (:py:func:`collections.namedtuple`).

    Parameters
    ----------
    obj

    Examples
    --------
    >>> import typic
    >>> from collections import namedtuple
    >>>
    >>> FooTup = namedtuple("FooTup", ["bar"])
    >>> typic.isnamedtuple(FooTup)
    True
    """
    return inspect.isclass(obj) and issubclass(obj, tuple) and hasattr(obj, "_fields")


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


_ATTR_CHECKS = (inspect.isclass, inspect.isroutine, isproperty)


def issimpleattribute(v) -> bool:
    return not any(c(v) for c in _ATTR_CHECKS)


def isabstract(o) -> TypeGuard[abc.ABC]:
    return inspect.isabstract(o) or o in _ABCS


# Custom list of ABCs which incorrectly evaluate to false
_ABCS = frozenset({numbers.Number})


def istypicklass(obj) -> TypeGuard[TypicObjectT]:
    return hasattr(obj, "__typic_fields__")
