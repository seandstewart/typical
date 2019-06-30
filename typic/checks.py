#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import datetime
import enum
import functools
import inspect
from typing import Any, Optional, Union, Collection, Mapping, ClassVar


__all__ = (
    "BUILTIN_TYPES",
    "resolve_supertype",
    "isbuiltintype",
    "isclassvartype",
    "iscollectiontype",
    "isdatetype",
    "isenumtype",
    "isfromdictclass",
    "ismappingtype",
    "isoptionaltype",
)


# Python stdlib and Python documentation have no "definitive list" of builtin-**types**, despite the fact that they are
# well-known. The closest we have is https://docs.python.org/3.7/library/functions.html, which clumps the
# builtin-types with builtin-functions. Despite clumping these types with functions in the documentation, these types
# eval as False when compared to types.BuiltinFunctionType, which is meant to be an alias for the builtin-functions
# listed in the documentation.
#
# All this to say, here we are with a manually-defined set of builtin-types. This probably won't break anytime soon,
# but we shall see...
BUILTIN_TYPES = frozenset(
    (int, bool, float, str, bytes, bytearray, list, set, frozenset, tuple, dict)
)


@functools.lru_cache(maxsize=None)
def resolve_supertype(annotation: Any) -> Any:
    """Resolve NewTypes, recursively."""
    if hasattr(annotation, "__supertype__"):
        return resolve_supertype(annotation.__supertype__)
    return annotation


@functools.lru_cache(maxsize=None)
def isbuiltintype(obj: Any) -> bool:
    """Check whether the provided object is a builtin-type"""
    return (
        resolve_supertype(obj) in BUILTIN_TYPES
        or resolve_supertype(type(obj)) in BUILTIN_TYPES
    )


@functools.lru_cache(maxsize=None)
def isoptionaltype(obj: Any) -> bool:
    """Test whether an annotation is Optional"""
    args = getattr(obj, "__args__", ())
    return (
        len(args) == 2
        and args[-1]
        is type(None)  # noqa: E721 - we don't know what args[-1] is, so this is safer
        and getattr(obj, "__origin__", obj) in {Optional, Union}
    )


@functools.lru_cache(maxsize=None)
def isdatetype(obj: Any) -> bool:
    """Test whether this annotation is a a date/datetime object."""
    return obj in {datetime.datetime, datetime.date}


@functools.lru_cache(maxsize=None)
def iscollectiontype(obj: Any):
    """Test whether this annotation is a subclass of :py:class:`typing.Mapping`"""
    return inspect.isclass(obj) and issubclass(obj, Collection)


@functools.lru_cache(maxsize=None)
def ismappingtype(obj: Any):
    """Test whether this annotation is a subclass of :py:class:`typing.Mapping`"""
    return inspect.isclass(obj) and issubclass(obj, Mapping)


@functools.lru_cache(maxsize=None)
def isenumtype(obj: Any) -> bool:
    """Test whether this annotation is a subclass of :py:class:`enum.Enum`"""
    return inspect.isclass(obj) and issubclass(obj, enum.Enum)


@functools.lru_cache(maxsize=None)
def isclassvartype(obj: Any) -> bool:
    """Test whether an annotation is a ClassVar annotation."""
    return getattr(obj, "__origin__", obj) is ClassVar


@functools.lru_cache(maxsize=None)
def isfromdictclass(obj: Any) -> bool:
    """Test whether this annotation is a class with a ``from_dict()`` method."""
    return inspect.isclass(obj) and hasattr(obj, "from_dict")
