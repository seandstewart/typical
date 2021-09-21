from __future__ import annotations

import ast
import collections
import collections.abc
import dataclasses
import functools
import inspect
import sys
import types
import warnings
from datetime import date, datetime, timedelta, time
from threading import RLock
from types import MappingProxyType, MemberDescriptorType
import typing
from typing import (  # type: ignore  # ironic...
    Tuple,
    Any,
    Sequence,
    Collection,
    Mapping,
    Hashable,
    Type,
    TypeVar,
    Callable,
    get_type_hints as _get_type_hints,
    Union,
    MutableMapping,
    MutableSequence,
    Iterable,
    AbstractSet,
    MutableSet,
    Dict,
    Optional,
    _eval_type,
)

import pendulum
from future_typing import transform_annotation

import typic.checks as checks
from typic.compat import ForwardRef, lru_cache, KW_ONLY, get_origin
from typic.ext import json

__all__ = (
    "cached_issubclass",
    "cached_property",
    "cached_signature",
    "cached_simple_attributes",
    "cached_type_hints",
    "cachedmethod",
    "extract",
    "fastcachedmethod",
    "filtered_repr",
    "get_args",
    "get_name",
    "get_defname",
    "get_qualname",
    "get_tag_for_types",
    "get_type_hints",
    "get_unique_name",
    "isoformat",
    "origin",
    "resolve_supertype",
    "safe_eval",
    "safe_get_params",
    "signature",
    "simple_attributes",
    "slotted",
    "TaggedUnion",
    "typed_dict_signature",
    "TypeMap",
)

from typic.compat import SQLAMetaData, sqla_registry


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


@lru_cache(maxsize=2000, typed=True)
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


@lru_cache(maxsize=None)
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

    actual = get_origin(actual) or actual

    # provide defaults for generics
    if not checks.isbuiltintype(actual):
        actual = _check_generics(actual)

    if inspect.isroutine(actual):
        actual = collections.abc.Callable

    return actual


@lru_cache(maxsize=None)
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


@lru_cache(maxsize=None)
def get_name(obj: Union[Type, ForwardRef, Callable]) -> str:
    """Safely retrieve the name of either a standard object or a type annotation.

    Examples
    --------
    >>> import typic
    >>> from typing import Dict, Any
    >>> T = TypeVar("T")
    >>> typic.get_name(Dict)
    'Dict'
    >>> typic.get_name(Dict[str, str])
    'Dict'
    >>> typic.get_name(Any)
    'Any'
    >>> typic.get_name(dict)
    'dict'
    """
    strobj = get_qualname(obj)
    return strobj.rsplit(".")[-1]


@lru_cache(maxsize=None)
def get_qualname(obj: Union[Type, ForwardRef, Callable]) -> str:
    """Safely retrieve the qualname of either a standard object or a type annotation.

    Examples
    --------
    >>> import typic
    >>> from typing import Dict, Any
    >>> T = TypeVar("T")
    >>> typic.get_qualname(Dict)
    'typing.Dict'
    >>> typic.get_qualname(Dict[str, str])
    'typing.Dict'
    >>> typic.get_qualname(Any)
    'typing.Any'
    >>> typic.get_qualname(dict)
    'dict'
    """
    strobj = str(obj)
    if isinstance(obj, ForwardRef):
        strobj = str(obj.__forward_arg__)
    isgeneric = (
        strobj.startswith("typing.")
        or strobj.startswith("typing_extensions.")
        or "[" in strobj
    )
    # We got a typing thing.
    if isgeneric:
        # If this is a subscripted generic we should clean that up.
        return strobj.split("[")[0]
    # Easy-ish path, use name magix
    if hasattr(obj, "__qualname__") and obj.__qualname__:  # type: ignore
        qualname = obj.__qualname__  # type: ignore
        if "<locals>" in qualname:
            return qualname.rsplit(".")[-1]
        return qualname
    if hasattr(obj, "__name__") and obj.__name__:  # type: ignore
        return obj.__name__  # type: ignore
    return strobj


@lru_cache(maxsize=None)
def get_unique_name(obj: Type) -> str:
    return f"{get_name(obj)}_{id(obj)}".replace("-", "_")


@lru_cache(maxsize=None)
def get_defname(pre: str, obj: Hashable) -> str:
    return f"{pre}_{hash(obj)}".replace("-", "_")


@lru_cache(maxsize=None)
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


def signature(obj: Union[Callable, Type]) -> inspect.Signature:
    """Get the signature of a type or callable.

    Also supports TypedDict subclasses
    """
    return (
        typed_dict_signature(obj)
        if checks.istypeddict(obj)  # type: ignore
        else inspect.signature(obj)
    )


cached_signature = lru_cache(maxsize=None)(signature)


def _safe_get_type_hints(annotation: Union[Type, Callable]) -> Dict[str, Type[Any]]:
    raw_annotations: Dict[str, Any] = {}
    base_globals: Dict[str, Any] = {"typing": typing}
    if isinstance(annotation, type):
        for base in reversed(annotation.__mro__):
            base_globals.update(sys.modules[base.__module__].__dict__)
            raw_annotations.update(getattr(base, "__annotations__", None) or {})
    else:
        raw_annotations = getattr(annotation, "__annotations__", None) or {}
        module_name = getattr(annotation, "__module__", None)
        if module_name:
            base_globals.update(sys.modules[module_name].__dict__)
    annotations = {}
    for name, value in raw_annotations.items():
        if isinstance(value, str):
            value = transform_annotation(value)
            if sys.version_info >= (3, 7):
                value = ForwardRef(value, is_argument=False)
            else:
                value = ForwardRef(value)
        try:
            value = _eval_type(value, base_globals or None, None)
        except NameError:
            # this is ok, we deal with it later.
            pass
        except TypeError as e:
            warnings.warn(f"Couldn't evaluate type {value!r}: {e}")
            value = Any
        annotations[name] = value
    return annotations


def get_type_hints(obj: Union[Type, Callable]) -> Dict[str, Type[Any]]:
    try:
        hints = _get_type_hints(obj)
    except (NameError, TypeError):
        hints = _safe_get_type_hints(obj)
    # KW_ONLY is a special sentinel to denote kw-only params in a dataclass.
    #  We don't want to do anything with this hint/field. It's not real.
    return {f: t for f, t in hints.items() if t is not KW_ONLY}


cached_type_hints = lru_cache(maxsize=None)(get_type_hints)


@lru_cache(maxsize=None)
def cached_issubclass(st: Type, t: Union[Type, Tuple[Type, ...]]) -> bool:
    """A cached result of :py:func:`issubclass`."""
    return issubclass(st, t)


def simple_attributes(t: Type) -> Tuple[str, ...]:
    """Extract all public, static data-attributes for a given type."""
    # If slots are defined, this is the best way to locate static attributes.
    if hasattr(t, "__slots__") and t.__slots__:
        return (
            *(
                f
                for f in t.__slots__
                if not f.startswith("_")
                # JIC - check if this is something fancy.
                and not isinstance(getattr(t, f, ...), _DYNAMIC_ATTRIBUTES)
            ),
        )
    # Otherwise we have to guess. This is inherently faulty, as attributes aren't
    #   always defined on a class before instantiation. The alternative is reverse
    #   engineering the constructor... yikes.
    return (
        *(
            x
            for x, y in inspect.getmembers(t, predicate=checks.issimpleattribute)
            if not x.startswith("_") and not isinstance(y, _DYNAMIC_ATTRIBUTES)
        ),
    )


_DYNAMIC_ATTRIBUTES = (SQLAMetaData, sqla_registry)


cached_simple_attributes = lru_cache(maxsize=None)(simple_attributes)
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


@lru_cache(maxsize=None)
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


def slotted(
    _cls: Type = None,
    *,
    dict: bool = True,
    weakref: bool = False,
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
        key = repr(cls)
        if key in _stack:
            raise TypeError(
                f"{cls!r} uses a custom metaclass {cls.__class__!r} "
                "which is not compatible with automatic slots. "
                "See Issue #104 on GitHub for more information."
            ) from None

        _stack.add(key)

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

        _stack.clear()
        return new_cls

    return wrap if _cls is None else wrap(_cls)


_stack: MutableSet[Type] = set()


class joinedrepr(str):
    __slots__ = ("fields", "__dict__")
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
        "__dict__",
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


@functools.lru_cache(maxsize=100_000)
def isoformat(t: Union[date, datetime, time, timedelta]) -> str:
    if isinstance(t, (date, datetime, time)):
        return t.isoformat()
    d = t
    if not isinstance(d, pendulum.Duration):
        d = pendulum.duration(
            days=t.days,
            seconds=t.seconds,
            microseconds=t.microseconds,
        )

    periods = [
        ("Y", d.years),
        ("M", d.months),
        ("D", d.remaining_days),
    ]
    period = "P"
    for sym, val in periods:
        period += f"{val}{sym}"
    times = [
        ("H", d.hours),
        ("M", d.minutes),
        ("S", d.remaining_seconds),
    ]
    time_ = "T"
    for sym, val in times:
        time_ += f"{val}{sym}"
    if d.microseconds:
        time_ = time_[:-1]
        time_ += f".{d.microseconds:06}S"
    return period + time_


@slotted(dict=False)
@dataclasses.dataclass(frozen=True)
class TaggedUnion:
    tag: str
    types: Tuple[Type, ...]
    isliteral: bool
    types_by_values: Tuple[Tuple[Any, Type], ...]


empty = object()


@functools.lru_cache(maxsize=None)
def get_tag_for_types(types: Tuple[Type, ...]) -> Optional[TaggedUnion]:
    if any(
        t in {None, ...} or not inspect.isclass(t) or checks.isstdlibtype(t)
        for t in types
    ):
        return None
    if len(types) > 1:
        root = types[0]
        root_hints = cached_type_hints(root)
        intersection = {k for k in root_hints if not k.startswith("_")}
        fields_by_type = {root: root_hints}
        t: Type
        for t in types[1:]:
            hints = cached_type_hints(t)
            intersection &= hints.keys()
            fields_by_type[t] = hints
        tag = None
        literal = False
        # If we have an intersection, check if it's constant value we can use
        # TODO: This won't support Generics in this state.
        #  We don't support generics yet (#119), but when we do,
        #  we need to add a branch for tagged unions from generics.
        while intersection and tag is None:
            f = intersection.pop()
            v = getattr(root, f, empty)
            if (
                v is not empty
                and not isinstance(v, MemberDescriptorType)
                and checks.ishashable(v)
                and not checks.isdescriptor(v)
            ):
                tag = f
                continue
            rhint = root_hints[f]
            if checks.isliteral(rhint):
                tag, literal = f, True
        if tag:
            if literal:
                tbv = (
                    *((a, t) for t in types for a in get_args(fields_by_type[t][tag])),
                )
            else:
                tbv = (*((getattr(t, tag), t) for t in types),)
            return TaggedUnion(
                tag=tag, types=types, isliteral=literal, types_by_values=tbv
            )
    return None


def extract(name: str, *, frame: types.FrameType = None) -> Optional[Any]:
    """Extract `name` from the stacktrace of `frame`.

    If `frame` is not provided, this function will use the current frame.
    """
    frame = frame or inspect.currentframe()
    seen = set()
    while frame and frame not in seen:
        if name in frame.f_globals:
            return frame.f_globals[name]
        if name in frame.f_locals:
            return frame.f_locals[name]
        seen.add(frame)
        frame = frame.f_back

    return None
