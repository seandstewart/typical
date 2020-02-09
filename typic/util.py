#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import ast
import collections
import dataclasses
import datetime
import decimal
import enum
import functools
import inspect
import ipaddress
import pathlib
import re
import sys
import uuid
from collections.abc import Mapping as Mapping_abc, Collection as Collection_abc
from threading import RLock
from types import MappingProxyType
from typing import (
    Tuple,
    Any,
    Sequence,
    Collection,
    Mapping,
    Hashable,
    Type,
    TypeVar,
    Callable,
    get_type_hints,
    Union,
)

import typic.checks as checks

__all__ = (
    "cached_property",
    "cached_signature",
    "cached_type_hints",
    "cachedmethod",
    "fastcachedmethod",
    "filtered_repr",
    "get_args",
    "get_name",
    "hexhash",
    "origin",
    "primitive",
    "resolve_supertype",
    "safe_eval",
    "typed_dict_signature",
)


def _get_loader():  # pragma: nocover
    try:
        import ujson

        return ujson.loads

    except ImportError:  # pragma: nocover
        import json

        return json.loads


load = _get_loader()

GENERIC_TYPE_MAP = {
    collections.abc.Sequence: list,
    Sequence: list,
    collections.abc.Collection: list,
    Collection: list,
    Mapping: dict,
    collections.abc.Mapping: dict,
    Hashable: str,
    collections.abc.Hashable: str,
}


def hexhash(*args, __order=sys.byteorder, **kwargs) -> str:
    return hash(f"{args}{kwargs}").to_bytes(8, __order, signed=True).hex()


@functools.lru_cache(maxsize=2000, typed=True)
def safe_eval(string: str) -> Tuple[bool, Any]:
    """Try a few methods to evaluate a string and get the correct Python data-type.

    Return the result and an indicator for whether we could do anything with it.

    Examples
    --------
    >>> safe_eval('{"foo": null}')
    (True, {'foo': None})

    Parameters
    ----------
    string
        The string to attempt to evaluate into a valid Python data-structure or object

    Returns
    -------
    processed :
        Whether we successfully evaluated the string
    result :
        The final result of the operation
    """
    try:
        result, processed = ast.literal_eval(string), True
    except (TypeError, ValueError, SyntaxError):
        try:
            result, processed = load(string), True
        except (TypeError, ValueError, SyntaxError):
            result, processed = string, False

    return processed, result


def _check_generics(hint: Any):
    return GENERIC_TYPE_MAP.get(hint, hint)


def filtered_repr(self) -> str:
    return f"{type(self).__name__}{filtered_str(self)}"


def filtered_str(self) -> str:
    fields = []
    for f in dataclasses.fields(self):
        val = getattr(self, f.name)
        if (val or val in {False, 0}) and f.repr:
            fields.append(f"{f.name}={val!r}")
    return f"({', '.join(fields)})"


@functools.lru_cache(maxsize=None)
def origin(annotation: Any) -> Any:
    """Get the highest-order 'origin'-type for subclasses of typing._SpecialForm.

    For the purposes of this library, if we can resolve to a builtin type, we will.

    Examples
    --------
    >>> import typic
    >>> from typing import Dict, Mapping, NewType, Optional
    >>> typic.origin(Dict)
    <class 'dict'>
    >>> typic.origin(Mapping)
    <class 'dict'>
    >>> Registry = NewType('Registry', Dict)
    >>> typic.origin(Registry)
    <class 'dict'>
    >>> class Foo: ...
    ...
    >>> typic.origin(Foo)
    <class 'typic.util.Foo'>
    """
    # Resolve custom NewTypes.
    actual = resolve_supertype(annotation)

    # Unwrap optional/classvar
    if checks.isclassvartype(actual):
        args = get_args(actual)
        actual = args[0] if args else actual

    # Extract the highest-order origin of the annotation.
    while hasattr(actual, "__origin__"):
        actual = actual.__origin__

    # provide defaults for generics
    if not checks.isbuiltintype(actual):
        actual = _check_generics(actual)

    return actual


@functools.lru_cache(maxsize=None)
def get_args(annotation: Any) -> Tuple[Any, ...]:
    """Get the args supplied to an annotation, excluding :py:class:`typing.TypeVar`.

    Examples
    --------
    >>> import typic
    >>> from typing import Dict, TypeVar
    >>> T = TypeVar("T")
    >>> typic.get_args(Dict)
    ()
    >>> typic.get_args(Dict[str, int])
    (<class 'str'>, <class 'int'>)
    >>> typic.get_args(Dict[str, T])
    (<class 'str'>,)
    """
    return (
        *(x for x in getattr(annotation, "__args__", ()) if type(x) is not TypeVar),
    )


@functools.lru_cache(maxsize=None)
def get_name(obj: Type) -> str:
    """Safely retrieve the name of either a standard object or a type annotation.

    Examples
    --------
    >>> import typic
    >>> from typing import Dict, Any
    >>> T = TypeVar("T")
    >>> typic.get_name(Dict)
    'Dict'
    >>> typic.get_name(Any)
    'Any'
    >>> typic.get_name(dict)
    'dict'
    """
    if hasattr(obj, "_name"):
        return obj._name
    return obj.__name__


@functools.lru_cache(maxsize=None)
def resolve_supertype(annotation: Type[Any]) -> Any:
    """Get the highest-order supertype for a NewType.

    Examples
    --------
    >>> import typic
    >>> from typing import NewType
    >>> UserID = NewType("UserID", int)
    >>> AdminID = NewType("AdminID", UserID)
    >>> typic.resolve_supertype(AdminID)
    <class 'int'>
    """
    while hasattr(annotation, "__supertype__"):
        annotation = annotation.__supertype__
    return annotation


class cached_property:  # type: ignore
    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
        self.lock = RLock()

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        attrname = self.func.__name__
        try:
            cache = instance.__dict__
        # objects with __slots__ have no __dict__
        except AttributeError:  # pragma: nocover
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {attrname!r} property."
            )
            raise TypeError(msg) from None
        with self.lock:
            # check if another thread filled cache while we awaited lock
            if attrname not in cache:
                cache[attrname] = self.func(instance)
        return cache[attrname]


# stolen from functools._HashedSeq
class __HashedSeq(list):

    __slots__ = "hashvalue"

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue


# Stolen approximately from functools._make_key
# Should try to find a faster way to do this.
def _make_key(
    args,
    kwds,
    kwd_mark=(object(),),
    fasttypes=frozenset({int, str}),
    type=type,
    len=len,
):
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return __HashedSeq(key)


_T = TypeVar("_T")


def cachedmethod(func: Callable[..., _T]) -> Callable[..., _T]:
    """Thread-safe caching of the result of an instance method.

    Mimics some of the pure-Python implementation of :py:func:`functools.lru_cache`.
    Major differences are that it's un-bounded in size and no direct access to the cache.
    It's also slower, being that it's pure-Python and the actual ``_lru_cache_wrapper``
    is implemented in C.
    """

    cache = func.__dict__
    cacheget = cache.get
    makekey = _make_key
    sentinel = object()
    lock = RLock()

    @functools.wraps(func)
    def _cached_method_wrapper(*args, **kwargs) -> _T:
        nonlocal cache
        key = makekey(args[1:], kwargs)
        result = cacheget(key, sentinel)
        if result is not sentinel:
            return result
        with lock:
            result = func(*args, **kwargs)
            cache[key] = result
        return result

    return _cached_method_wrapper


def fastcachedmethod(func):
    """Super-fast memoization of a method.

    Notes
    -----
    This is limited to a method that takes only one arg and is un-bounded in size.

    Examples
    --------
    >>> import typic
    >>>
    >>> class Foo:
    ...     @typic.fastcachedmethod
    ...     def bar(self, num: int) -> int:
    ...         return num * (num + 1)
    ...
    """

    class memodict(dict):
        __slots__ = ()

        def __missing__(self, key):
            self[key] = ret = func(instance, key)
            return ret

    sentinel = object()
    memo = memodict()
    memoget = memo.__getitem__
    instance = sentinel

    @functools.wraps(func)
    def _fast_cached_method_wrapper(inst, arg):
        nonlocal instance
        instance = inst
        return memoget(arg)

    _fast_cached_method_wrapper.cache_clear = memo.clear
    _fast_cached_method_wrapper.cache_size = memo.__len__
    _fast_cached_method_wrapper.cache_view = lambda: MappingProxyType(memo)

    return _fast_cached_method_wrapper


@functools.lru_cache(maxsize=None)
def cached_signature(obj: Callable) -> inspect.Signature:
    """A cached result of :py:func:`inspect.signature`.

    Building the function signature is notoriously slow, but we can be safe that the
    signature won't change at runtime, so we cache the result.

    We also provide a little magic so that we can introspect the new :py:class:`TypedDict`
    """
    return (
        typed_dict_signature(obj) if checks.istypeddict(obj) else inspect.signature(obj)
    )


@functools.lru_cache(maxsize=None)
def cached_type_hints(obj: Callable) -> dict:
    """A cached result of :py:func:`typing.get_type_hints`.

    We don't want to go through the process of resolving type-hints every time.
    """
    return get_type_hints(obj)


def typed_dict_signature(obj: Callable) -> inspect.Signature:
    """A little faker for getting the "signature" of a :py:class:`TypedDict`.

    Technically, these are dicts at runtime, but we are enforcing a static shape,
    so we should be able to declare a matching signature for it.
    """
    hints = cached_type_hints(obj)
    return inspect.Signature(
        parameters=tuple(
            inspect.Parameter(
                name=x,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=y,
                default=getattr(obj, x, inspect.Parameter.empty),
            )
            for x, y in hints.items()
        )
    )


DEFAULT_ENCODING = "utf-8"


@functools.singledispatch
def primitive(obj: Any) -> Any:
    """A single-dispatch function for converting an object to its primitive equivalent.

    Useful for encoding data to JSON.

    Registration for custom types may be done by wrapping your handler with
    `@primitive.register`

    Examples
    --------
    >>> import typic
    >>> import datetime
    >>> import uuid
    >>> import ipaddress
    >>> import re
    >>> import dataclasses
    >>> typic.primitive("foo")
    'foo'
    >>> typic.primitive(("foo",))  # containers are converted to lists/dicts
    ['foo']
    >>> typic.primitive(datetime.datetime(1970, 1, 1))  # note that we assume UTC
    '1970-01-01T00:00:00+00:00'
    >>> typic.primitive(b"foo")
    'foo'
    >>> typic.primitive(ipaddress.IPv4Address("0.0.0.0"))
    '0.0.0.0'
    >>> typic.primitive(re.compile("[0-9]"))
    '[0-9]'
    >>> typic.primitive(uuid.UUID(int=0))
    '00000000-0000-0000-0000-000000000000'
    >>> @dataclasses.dataclass
    ... class Foo:
    ...     bar: str = 'bar'
    ...
    >>> typic.primitive(Foo())
    {'bar': 'bar'}
    """
    if isinstance(obj, enum.Enum):
        obj = obj.value
    return _primitive(obj)


@functools.singledispatch
def _primitive(obj: Any) -> Any:

    # Common methods found in classes for dumping to dicts
    if hasattr(obj, "asdict"):
        return primitive(obj.asdict())
    if hasattr(obj, "to_dict"):
        return primitive(obj.to_dict())
    # Dataclasses, duh.
    if dataclasses.is_dataclass(obj):
        return primitive(dataclasses.asdict(obj))
    raise ValueError(f"Can't determine primitive from type {type(obj)!r}")


IPvAnyType = Union[
    ipaddress.IPv4Address,
    ipaddress.IPv6Interface,
    ipaddress.IPv4Network,
    ipaddress.IPv6Address,
    ipaddress.IPv6Interface,
    ipaddress.IPv6Network,
]


@_primitive.register(str)  # type: ignore
@_primitive.register(int)
@_primitive.register(bool)
@_primitive.register(float)
@_primitive.register(type(None))
def _(obj):
    return obj


@_primitive.register(dict)  # type: ignore
@_primitive.register(Mapping_abc)
@_primitive.register(MappingProxyType)
def _(obj):
    return {primitive(x): primitive(y) for x, y in obj.items()}


@_primitive.register(list)  # type: ignore
@_primitive.register(tuple)
@_primitive.register(set)
@_primitive.register(frozenset)
@_primitive.register(Collection_abc)
def _(obj):
    return [primitive(x) for x in obj]


@_primitive.register(bytes)  # type: ignore
@_primitive.register(bytearray)
def _(obj):
    return obj.decode(DEFAULT_ENCODING)


@_primitive.register(ipaddress.IPv4Address)  # type: ignore
@_primitive.register(ipaddress.IPv4Interface)
@_primitive.register(ipaddress.IPv4Network)
@_primitive.register(ipaddress.IPv6Address)
@_primitive.register(ipaddress.IPv6Interface)
@_primitive.register(ipaddress.IPv6Network)
@_primitive.register(pathlib.Path)
@_primitive.register(uuid.UUID)
def _(obj: Union[IPvAnyType, pathlib.Path, uuid.UUID]) -> str:
    return str(obj)


@_primitive.register(datetime.datetime)  # type: ignore
@_primitive.register(datetime.date)
@_primitive.register(datetime.time)
def _(obj: Union[datetime.datetime, datetime.date, datetime.time]) -> str:
    if isinstance(obj, (datetime.datetime, datetime.time)) and not obj.tzinfo:
        return f"{obj.isoformat()}+00:00"
    return obj.isoformat()


@_primitive.register(re.Pattern)  # type: ignore
def _(obj: re.Pattern) -> str:  # type: ignore
    return obj.pattern


@_primitive.register(decimal.Decimal)  # type: ignore
def _(obj: decimal.Decimal) -> float:
    return float(obj)
