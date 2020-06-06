#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import datetime
import decimal
import enum
import functools
import inspect
import ipaddress
import pathlib
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
)

import typic
import typic.common
import typic.util as util
import typic.strict as strict

from typic.compat import Final

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
    "isbuiltininstance",
    "isbuiltintype",
    "isbuiltinsubtype",
    "isclassvartype",
    "iscollectiontype",
    "isconstrained",
    "isdatetype",
    "isenumtype",
    "isfinal",
    "isfromdictclass",
    "isfrozendataclass",
    "ishashable",
    "isinstance",
    "ismappingtype",
    "isnamedtuple",
    "isoptionaltype",
    "isreadonly",
    "issimpleattribute",
    "isstrict",
    "isstdlibinstance",
    "isstdlibtype",
    "isstdlibsubtype",
    "issubclass",
    "istypeddict",
    "istypedtuple",
    "iswriteonly",
    "should_unwrap",
)


# Here we are with a manually-defined set of builtin-types.
# This probably won't break anytime soon, but we shall see...
BUILTIN_TYPES = frozenset(
    (
        int,
        bool,
        float,
        str,
        bytes,
        bytearray,
        list,
        set,
        frozenset,
        tuple,
        dict,
        type(None),
    )
)
BUILTIN_TYPES_TUPLE = tuple(BUILTIN_TYPES)
STDLIB_TYPES = frozenset(
    (
        *BUILTIN_TYPES,
        datetime.datetime,
        datetime.date,
        decimal.Decimal,
        pathlib.Path,
        ipaddress.IPv4Address,
        ipaddress.IPv6Address,
    )
)
STDLIB_TYPES_TUPLE = tuple(STDLIB_TYPES)


@functools.lru_cache(maxsize=None)
def isbuiltintype(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def isstdlibtype(obj: Type[ObjectT]) -> bool:
    return (
        util.resolve_supertype(obj) in STDLIB_TYPES
        or util.resolve_supertype(type(obj)) in STDLIB_TYPES
    )


@functools.lru_cache(maxsize=None)
def isbuiltinsubtype(t: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def isstdlibsubtype(t: Type[ObjectT]) -> bool:
    return issubclass(util.resolve_supertype(t), STDLIB_TYPES_TUPLE)


def isbuiltininstance(o: ObjectT) -> bool:
    return _isinstance(o, BUILTIN_TYPES_TUPLE)


def isstdlibinstance(o: ObjectT) -> bool:
    return _isinstance(o, STDLIB_TYPES_TUPLE)


@functools.lru_cache(maxsize=None)
def isoptionaltype(obj: Type[ObjectT]) -> bool:
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
        is type(None)  # noqa: E721 - we don't know what args[-1] is, so this is safer
        and getattr(obj, "__origin__", obj) in {Optional, Union}
    )


@functools.lru_cache(maxsize=None)
def isreadonly(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
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


@functools.lru_cache(maxsize=None)
def iswriteonly(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def isstrict(obj: Type[ObjectT]) -> bool:
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
    return util.origin(obj) is strict.Strict


@functools.lru_cache(maxsize=None)
def isdatetype(obj: Type[ObjectT]) -> bool:
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
    return _issubclass(util.origin(obj), (datetime.datetime, datetime.date))


_COLLECTIONS = {list, set, tuple, frozenset, dict, str, bytes}


@functools.lru_cache(maxsize=None)
def iscollectiontype(obj: Type[ObjectT]):
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
    return obj in _COLLECTIONS or _issubclass(obj, Collection)


@functools.lru_cache(maxsize=None)
def ismappingtype(obj: Type[ObjectT]):
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
    return _issubclass(obj, dict) or _issubclass(obj, Mapping)


@functools.lru_cache(maxsize=None)
def isenumtype(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def isclassvartype(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def should_unwrap(obj: Type[ObjectT]) -> bool:
    """Test whether we should use the __args__ attr for resolving the type.

    This is useful for determining what type to use at run-time for coercion.
    """
    return any(x(obj) for x in _UNWRAPPABLE)


@functools.lru_cache(maxsize=None)
def isfromdictclass(obj: Type[ObjectT]) -> bool:
    """Test whether this annotation is a class with a `from_dict()` method."""
    return inspect.isclass(obj) and hasattr(obj, "from_dict")


@functools.lru_cache(maxsize=None)
def isfrozendataclass(obj: Type[ObjectT]) -> bool:
    """Test whether this is a dataclass and whether it's frozen."""
    return getattr(getattr(obj, "__dataclass_params__", None), "frozen", False)


_isinstance = isinstance


@functools.lru_cache(maxsize=None)
def _type_check(t) -> bool:
    if _isinstance(t, tuple):
        return all(_type_check(x) for x in t)
    return inspect.isclass(t)


def isinstance(o: Any, t: Union[Type[ObjectT], Tuple[Type[ObjectT], ...]]) -> bool:
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
    return _type_check(t) and _isinstance(o, t)


_issubclass = issubclass


def issubclass(
    o: Type[Any], t: Union[Type[ObjectT], Tuple[Type[ObjectT], ...]]
) -> bool:
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
    return _type_check(t) and _type_check(o) and _issubclass(o, t)


@functools.lru_cache(maxsize=None)
def isconstrained(obj: Type[ObjectT]) -> bool:
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


__hashgetter = attrgetter("__hash__")


def ishashable(obj: ObjectT) -> bool:
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


@functools.lru_cache(maxsize=None)
def istypeddict(obj: Type[ObjectT]) -> bool:
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
        and hasattr(obj, "__annotations__")
    )


@functools.lru_cache(maxsize=None)
def istypedtuple(obj: Type[ObjectT]) -> bool:
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


@functools.lru_cache(maxsize=None)
def isnamedtuple(obj: Type[ObjectT]) -> bool:
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


def isproperty(obj) -> bool:
    return obj.__class__.__name__ in {"property", "cached_property"}


_ATTR_CHECKS = (inspect.isclass, inspect.isroutine, isproperty)


def issimpleattribute(v) -> bool:
    return not any(c(v) for c in _ATTR_CHECKS)
