from __future__ import annotations

import collections
import collections.abc
import dataclasses
import inspect
import sys
import types
import typing
import warnings
from types import MemberDescriptorType
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Dict,
    Hashable,
    Iterable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from typing import get_args as _get_args
from typing import get_origin
from typing import get_type_hints as _get_type_hints

from future_typing import transform_annotation

from typical import checks as checks
from typical.classes import slotted
from typical.compat import (
    KW_ONLY,
    ForwardRef,
    SQLAMetaData,
    eval_type,
    lru_cache,
    sqla_registry,
)
from typical.core import constants

__all__ = (
    "origin",
    "get_args",
    "get_name",
    "get_qualname",
    "get_unique_name",
    "get_defname",
    "resolve_supertype",
    "signature",
    "cached_signature",
    "get_type_hints",
    "cached_type_hints",
    "cached_issubclass",
    "simple_attributes",
    "cached_simple_attributes",
    "typed_dict_signature",
    "tuple_signature",
    "safe_get_params",
    "get_tag_for_types",
    "TaggedUnion",
    "TypeMap",
    "extract",
    "normalize_typevar",
)


@lru_cache(maxsize=None)
def origin(annotation: Any) -> Any:
    """Get the highest-order 'origin'-type for subclasses of typing._SpecialForm.

    For the purposes of this library, if we can resolve to a builtin type, we will.

    Examples
    --------
    >>> from typical import inspection
    >>> from typing import Dict, Mapping, NewType, Optional
    >>> inspection.origin(Dict)
    <class 'dict'>
    >>> inspection.origin(Mapping)
    <class 'dict'>
    >>> Registry = NewType('Registry', Dict)
    >>> inspection.origin(Registry)
    <class 'dict'>
    >>> class Foo: ...
    ...
    >>> inspection.origin(Foo)
    <class 'typical.inspection.Foo'>
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
        actual = Callable

    return actual


def _check_generics(hint: Any):
    return GENERIC_TYPE_MAP.get(hint, hint)


GENERIC_TYPE_MAP: dict[type, type] = {
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


@lru_cache(maxsize=None)
def get_args(annotation: Any) -> Tuple[Any, ...]:
    """Get the args supplied to an annotation, excluding :py:class:`typing.TypeVar`.

    Examples
    --------
    >>> from typical import inspection
    >>> from typing import Dict, TypeVar
    >>> T = TypeVar("T")
    >>> inspection.get_args(Dict)
    ()
    >>> inspection.get_args(Dict[str, int])
    (<class 'str'>, <class 'int'>)
    >>> inspection.get_args(Dict[str, T])
    (<class 'str'>,)
    """
    args = _get_args(annotation)
    return (*_normalize_typevars(*args),)


def _normalize_typevars(*args: Any) -> Iterable:
    for t in args:
        if type(t) is TypeVar:
            yield normalize_typevar(tvar=t)
        else:
            yield t


@lru_cache(maxsize=None)
def normalize_typevar(tvar: TypeVar):
    """Reduce a TypeVar to a simple type."""
    if tvar.__bound__:
        return tvar.__bound__
    elif tvar.__constraints__:
        return Union[tvar.__constraints__]
    return Any


@lru_cache(maxsize=None)
def get_name(obj: Union[Type, ForwardRef, Callable]) -> str:
    """Safely retrieve the name of either a standard object or a type annotation.

    Examples
    --------
    >>> from typical import inspection
    >>> from typing import Dict, Any
    >>> T = TypeVar("T")
    >>> inspection.get_name(Dict)
    'Dict'
    >>> inspection.get_name(Dict[str, str])
    'Dict'
    >>> inspection.get_name(Any)
    'Any'
    >>> inspection.get_name(dict)
    'dict'
    """
    strobj = get_qualname(obj)
    return strobj.rsplit(".")[-1]


@lru_cache(maxsize=None)
def get_qualname(obj: Union[Type, ForwardRef, Callable]) -> str:
    """Safely retrieve the qualname of either a standard object or a type annotation.

    Examples
    --------
    >>> from typical import inspection
    >>> from typing import Dict, Any
    >>> T = TypeVar("T")
    >>> inspection.get_qualname(Dict)
    'typing.Dict'
    >>> inspection.get_qualname(Dict[str, str])
    'typing.Dict'
    >>> inspection.get_qualname(Any)
    'typing.Any'
    >>> inspection.get_qualname(dict)
    'dict'
    """
    strobj = str(obj)
    if isinstance(obj, ForwardRef):
        strobj = str(obj.__forward_arg__)
    isgeneric = checks.isgeneric(strobj)
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
def resolve_supertype(annotation: Type[Any] | types.FunctionType) -> Any:
    """Get the highest-order supertype for a NewType.

    Examples
    --------
    >>> from typical import inspection
    >>> from typing import NewType
    >>> UserID = NewType("UserID", int)
    >>> AdminID = NewType("AdminID", UserID)
    >>> inspection.resolve_supertype(AdminID)
    <class 'int'>
    """
    while hasattr(annotation, "__supertype__"):
        annotation = annotation.__supertype__  # type: ignore[union-attr]
    return annotation


def signature(obj: Union[Callable, Type]) -> inspect.Signature:
    """Get the signature of a type or callable.

    Also supports TypedDict subclasses
    """
    if inspect.isclass(obj) or checks.isgeneric(obj):
        if checks.istypeddict(obj):
            return typed_dict_signature(obj)
        if checks.istupletype(obj) and not checks.isnamedtuple(obj):
            return tuple_signature(obj)
    return inspect.signature(obj)


cached_signature = lru_cache(maxsize=None)(signature)


def get_type_hints(
    obj: Union[Type, Callable], exhaustive: bool = True
) -> Dict[str, Type[Any]]:
    try:
        hints = _get_type_hints(obj)
    except (NameError, TypeError):
        hints = _safe_get_type_hints(obj)
    # KW_ONLY is a special sentinel to denote kw-only params in a dataclass.
    #  We don't want to do anything with this hint/field. It's not real.
    hints = {f: t for f, t in hints.items() if t is not KW_ONLY}
    if not hints and exhaustive:
        hints = _hints_from_signature(obj)
    return hints


def _hints_from_signature(obj: Union[Type, Callable]) -> Dict[str, Type[Any]]:
    try:
        globalns, _ = _get_globalns(obj)
        params: dict[str, inspect.Parameter] = {**signature(obj).parameters}
    except (TypeError, ValueError):
        return {}
    hints = {}
    for name, param in params.items():
        annotation = param.annotation
        if annotation is param.empty:
            annotation = Any
            hints[name] = annotation
            continue
        if annotation.__class__ is str:
            ref = ForwardRef(transform_annotation(annotation))
            try:
                annotation = eval_type(ref, globalns or None, None)
            except NameError:
                annotation = ref
            hints[name] = annotation
            continue
        hints[name] = annotation
    return hints


def _safe_get_type_hints(annotation: Union[Type, Callable]) -> Dict[str, Type[Any]]:
    base_globals, raw_annotations = _get_globalns(annotation)
    annotations = {}
    for name, value in raw_annotations.items():
        if isinstance(value, str):
            value = transform_annotation(value)
            if not isinstance(value, ForwardRef):
                if sys.version_info >= (3, 9, 8) and sys.version_info[:3] != (3, 10, 0):
                    value = ForwardRef(  # type: ignore
                        value,
                        is_argument=False,
                        is_class=inspect.isclass(annotation),
                    )
                elif sys.version_info >= (3, 7):
                    value = ForwardRef(value, is_argument=False)
                else:
                    value = ForwardRef(value)
        try:
            value = eval_type(value, base_globals or None, None)
        except NameError:
            # this is ok, we deal with it later.
            pass
        except TypeError as e:
            warnings.warn(f"Couldn't evaluate type {value!r}: {e}")
            value = Any
        annotations[name] = value
    return annotations


def _get_globalns(
    annotation: Union[Type, Callable]
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    return base_globals, raw_annotations


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


def typed_dict_signature(obj: Callable) -> inspect.Signature:
    """A little faker for getting the "signature" of a :py:class:`TypedDict`.

    Technically, these are dicts at runtime, but we are enforcing a static shape,
    so we should be able to declare a matching signature for it.
    """
    hints = cached_type_hints(obj)
    total = getattr(obj, "__total__", True)
    default = inspect.Parameter.empty if total else ...
    return inspect.Signature(
        parameters=tuple(
            inspect.Parameter(
                name=x,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=y,
                default=getattr(obj, x, default),
            )
            for x, y in hints.items()
        )
    )


def tuple_signature(t: type[tuple]) -> inspect.Signature:
    args = get_args(t)
    if not args or args[-1] is ...:
        argt = Any if not args else args[0]
        param = inspect.Parameter(
            name="args", kind=inspect.Parameter.VAR_POSITIONAL, annotation=argt
        )
        sig = inspect.Signature(parameters=(param,))
        return sig
    kind = inspect.Parameter.POSITIONAL_ONLY
    params = tuple(
        inspect.Parameter(name=f"arg{str(i)}", kind=kind, annotation=at)
        for i, at in enumerate(args)
    )
    sig = inspect.Signature(parameters=params)
    return sig


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


@lru_cache(maxsize=None)
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
            v = getattr(root, f, constants.empty)
            if (
                v is not constants.empty
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


@slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True)
class TaggedUnion:
    tag: str
    types: Tuple[Type, ...]
    isliteral: bool
    types_by_values: Tuple[Tuple[Any, Type], ...]


@lru_cache(maxsize=None)
def flatten_union(t: _UnionT) -> _UnionT | None:
    stack = collections.deque([t])
    args = {}
    while stack:
        u = stack.popleft()
        uargs = get_args(u)
        for a in uargs:
            if a in args:
                continue
            if checks.isuniontype(a):
                stack.append(a)
                continue
            args[a] = ...
    if not args:
        return None
    return typing.cast("_UnionT", Union[tuple(args)])


_UnionT = TypeVar("_UnionT")
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
            for ptype in t.__bases__:
                if ptype in self:
                    v = self[ptype]
                    # Cache for later use
                    self[t] = v
                    return v
        except (AttributeError, TypeError):
            pass

        return default


def extract(name: str, *, frame: types.FrameType = None) -> Optional[Any]:
    """Extract `name` from the stacktrace of `frame`.

    If `frame` is not provided, this function will use the current frame.
    """
    frame = frame or inspect.currentframe()
    seen: set[types.FrameType] = set()
    add = seen.add
    while frame and frame not in seen:
        if name in frame.f_globals:
            return frame.f_globals[name]
        if name in frame.f_locals:
            return frame.f_locals[name]
        add(frame)
        frame = frame.f_back

    return None
