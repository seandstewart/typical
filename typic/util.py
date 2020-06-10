#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import ast
import collections
import dataclasses
import functools
import inspect
import sys
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
    MutableMapping,
    MutableSequence,
    Iterable,
    AbstractSet,
    MutableSet,
    Dict,
    Optional,
)

import typic.checks as checks
from typic.ext import json

__all__ = (
    "cached_issubclass",
    "cached_property",
    "cached_signature",
    "cached_simple_attributes",
    "cached_type_hints",
    "cachedmethod",
    "fastcachedmethod",
    "filtered_repr",
    "get_args",
    "get_name",
    "hexhash",
    "origin",
    "resolve_supertype",
    "safe_eval",
    "safe_get_params",
    "simple_attributes",
    "slotted",
    "typed_dict_signature",
)

from typic.compat import SQLAMetaData


GENERIC_TYPE_MAP = {
    Sequence: list,
    MutableSequence: list,
    collections.abc.Sequence: list,
    collections.abc.MutableSequence: list,
    Collection: list,
    collections.abc.Collection: list,
    Iterable: list,
    collections.abc.Iterable: list,
    AbstractSet: set,
    MutableSet: set,
    collections.abc.Set: set,
    collections.abc.MutableSet: set,
    Mapping: dict,
    MutableMapping: dict,
    collections.abc.Mapping: dict,
    collections.abc.MutableMapping: dict,
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
            result, processed = json.loads(string), True
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
    if hasattr(obj, "_name") and not hasattr(obj, "__name__"):
        return obj._name
    return obj.__name__


@functools.lru_cache(maxsize=None)
def get_qualname(obj: Type) -> str:
    if hasattr(obj, "_name") and not hasattr(obj, "__name__"):
        return repr(obj)

    qualname = getattr(obj, "__qualname__", obj.__name__)
    if "<locals>" in qualname:
        return obj.__name__
    return qualname


@functools.lru_cache(maxsize=None)
def get_unique_name(obj: Type) -> str:
    return f"{get_name(obj)}_{id(obj)}".replace("-", "_")


@functools.lru_cache(maxsize=None)
def get_defname(pre: str, obj: Hashable) -> str:
    return f"{pre}_{hash(obj)}".replace("-", "_")


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
class __HashedSeq(list):  # pragma: nocover

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
):  # pragma: nocover
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return __HashedSeq(key)


_T = TypeVar("_T")


def cachedmethod(func: Callable[..., _T]) -> Callable[..., _T]:  # pragma: nocover
    """Thread-safe caching of the result of an instance method.

    Mimics some of the pure-Python implementation of :py:func:`functools.lru_cache`.
    Major differences are that it's un-bounded in size and no direct access to the cache.
    It's also slower, being that it's pure-Python and the actual `_lru_cache_wrapper`
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
    _fast_cached_method_wrapper._cache = memo

    return _fast_cached_method_wrapper


@functools.lru_cache(maxsize=None)
def cached_signature(obj: Callable) -> inspect.Signature:
    """A cached result of :py:func:`inspect.signature`.

    Building the function signature is notoriously slow, but we can be safe that the
    signature won't change at runtime, so we cache the result.

    We also provide a little magic so that we can introspect :py:class:`TypedDict`
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


@functools.lru_cache(maxsize=None)
def cached_issubclass(st: Type, t: Union[Type, Tuple[Type, ...]]) -> bool:
    """A cached result of :py:func:`issubclass`."""
    return issubclass(st, t)


def simple_attributes(t: Type) -> Tuple[str, ...]:
    """Extract all public, static data-attributes for a given type."""
    return (
        *(
            x
            for x, y in inspect.getmembers(t, predicate=checks.issimpleattribute)
            if not x.startswith("_") and not isinstance(y, SQLAMetaData)
        ),
    )


cached_simple_attributes = functools.lru_cache(maxsize=None)(simple_attributes)
"""A cached result of :py:func:`simple_attributes`."""


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


@functools.lru_cache(maxsize=None)
def safe_get_params(obj: Type) -> Mapping[str, inspect.Parameter]:
    params: Mapping[str, inspect.Parameter]
    try:
        if checks.issubclass(obj, Mapping) and not checks.istypeddict(obj):
            return {}
        params = cached_signature(obj).parameters
    except (ValueError, TypeError):  # pragma: nocover
        params = {}
    return params


VT = TypeVar("VT")


class TypeMap(Dict[Type, VT]):
    """A mapping of Type -> value."""

    def get_by_parent(self, t: Type, default: VT = None) -> Optional[VT]:
        """Traverse the MRO of a class, return the value for the nearest parent."""
        # Skip traversal if this type is already mapped.
        if t in self:
            return self[t]

        # Get the MRO - the first value is the given type so skip it
        try:
            for ptype in inspect.getmro(t)[1:]:
                if ptype in self:
                    v = self[ptype]
                    # Cache for later use
                    self[t] = v
                    return v
        except (AttributeError, TypeError):
            pass

        return default


def recursing() -> bool:
    """Detect whether we're in a recursive loop."""
    frames = inspect.getouterframes(inspect.currentframe())[1:]
    top_frame = inspect.getframeinfo(frames[0][0])
    for frame, _, _, _, _, _ in frames[1:]:
        (path, line_number, func_name, lines, index) = inspect.getframeinfo(frame)
        if path == top_frame[0] and func_name == top_frame[2]:
            return True
    return False


def slotted(
    _cls: Type = None, *, dict: bool = True, weakref: bool = False,
):
    """Decorator to create a "slotted" version of the provided class.

    Returns new class object as it's not possible to add __slots__ after class creation.

    Source: https://github.com/starhel/dataslots/blob/master/dataslots/__init__.py
    """

    def _slots_setstate(self, state):
        for param_dict in filter(None, state):
            for slot, value in param_dict.items():
                object.__setattr__(self, slot, value)

    def wrap(cls):
        cls_dict = {**cls.__dict__}
        # Create only missing slots
        inherited_slots = set().union(
            *(getattr(c, "__slots__", set()) for c in cls.mro())
        )

        field_names = {f.name for f in dataclasses.fields(cls)}
        if dict:
            field_names.add("__dict__")
        if weakref:
            field_names.add("__weakref__")
        cls_dict["__slots__"] = (*(field_names - inherited_slots),)

        # Erase filed names from class __dict__
        for f in field_names:
            cls_dict.pop(f, None)

        # Erase __dict__ and __weakref__
        cls_dict.pop("__dict__", None)
        cls_dict.pop("__weakref__", None)

        # Pickle fix for frozen dataclass as mentioned in https://bugs.python.org/issue36424
        # Use only if __getstate__ and __setstate__ are not declared and frozen=True
        if (
            all(param not in cls_dict for param in ["__getstate__", "__setstate__"])
            and cls.__dataclass_params__.frozen
        ):
            cls_dict["__setstate__"] = _slots_setstate

        # Prepare new class with slots
        new_cls = cls.__class__(cls.__name__, cls.__bases__, cls_dict)
        new_cls.__qualname__ = cls.__qualname__
        new_cls.__module__ = cls.__module__

        return new_cls

    return wrap if _cls is None else wrap(_cls)


class joinedrepr(str):
    __slots__ = ("fields",)
    fields: Iterable[Any]

    def __new__(cls, *fields):
        n = str.__new__(cls)
        n.fields = fields
        return n

    @cached_property
    def __repr(self) -> str:
        return ".".join(str(f) for f in self.fields)

    def __repr__(self) -> str:
        return self.__repr

    def __str__(self) -> str:
        return self.__repr


class collectionrepr(str):
    __slots__ = (
        "root_name",
        "keys",
    )
    root_name: str
    keys: Iterable[Any]

    def __new__(cls, root_name: "ReprT", *keys):
        n = str.__new__(cls)
        n.root_name = root_name
        n.keys = keys
        return n

    @cached_property
    def __repr(self) -> str:
        keys = "".join(f"[{o!r}]" for o in self.keys)
        return f"{self.root_name}{keys}"

    def __repr__(self) -> str:
        return self.__repr

    def __str__(self) -> str:
        return self.__repr


ReprT = Union[str, joinedrepr, collectionrepr]
