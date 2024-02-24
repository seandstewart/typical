from __future__ import annotations

import collections
import collections.abc
import dataclasses
import inspect
import operator
import reprlib
import sys
import types
import typing
import warnings
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Deque,
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

from typical import checks, classes, compat
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


@compat.lru_cache(maxsize=None)
def origin(annotation: Any) -> Any:
    """Get the highest-order 'origin'-type for subclasses of typing._SpecialForm.

    For the purposes of this library, if we can resolve to a builtin type, we will.

    Examples:
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

    actual = typing.get_origin(actual) or actual

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


@compat.lru_cache(maxsize=None)
def get_args(annotation: Any) -> Tuple[Any, ...]:
    """Get the args supplied to an annotation, excluding :py:class:`typing.TypeVar`.

    Examples:
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
    args = typing.get_args(annotation)
    if not args:
        args = getattr(annotation, "__args__", args)
        if not isinstance(args, Iterable):
            return ()

    return (*_normalize_typevars(*args),)


def _normalize_typevars(*args: Any) -> Iterable:
    for t in args:
        if type(t) is TypeVar:
            yield normalize_typevar(tvar=t)
        else:
            yield t


# Friendly alias for legacy purposes (used to have our own impl)
get_origin = typing.get_origin


@compat.lru_cache(maxsize=None)
def normalize_typevar(tvar: TypeVar) -> type[Any]:
    """Reduce a TypeVar to a simple type."""
    if tvar.__bound__:
        return tvar.__bound__
    elif tvar.__constraints__:
        return Union[tvar.__constraints__]  # type: ignore[return-value]
    return Any  # type: ignore[return-value]


@compat.lru_cache(maxsize=None)
def get_name(obj: Union[Type, compat.ForwardRef, Callable]) -> str:
    """Safely retrieve the name of either a standard object or a type annotation.

    Examples:
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


@compat.lru_cache(maxsize=None)
def get_qualname(obj: Union[Type, compat.ForwardRef, Callable]) -> str:
    """Safely retrieve the qualname of either a standard object or a type annotation.

    Examples:
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
    if isinstance(obj, compat.ForwardRef):
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


@compat.lru_cache(maxsize=None)
def get_unique_name(obj: Type) -> str:
    return f"{get_name(obj)}_{id(obj)}".replace("-", "_")


@compat.lru_cache(maxsize=None)
def get_defname(pre: str, obj: Hashable) -> str:
    return f"{pre}_{hash(obj)}".replace("-", "_")


@compat.lru_cache(maxsize=None)
def resolve_supertype(annotation: Type[Any] | types.FunctionType) -> Any:
    """Get the highest-order supertype for a NewType.

    Examples:
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


def signature(obj: Callable[..., Any] | type[Any]) -> inspect.Signature:
    """Get the signature of a type or callable.

    Also supports TypedDict subclasses
    """
    if inspect.isclass(obj) or checks.isgeneric(obj):
        if checks.istypeddict(obj):
            return typed_dict_signature(obj)
        if checks.istupletype(obj) and not checks.isnamedtuple(obj):
            return tuple_signature(obj)
    return inspect.signature(obj)


cached_signature = compat.lru_cache(maxsize=None)(signature)


def get_type_hints(
    obj: Union[Type, Callable], exhaustive: bool = True
) -> Dict[str, Type[Any]]:
    try:
        hints = typing.get_type_hints(obj)
    except (NameError, TypeError):
        hints = _safe_get_type_hints(obj)
    # KW_ONLY is a special sentinel to denote kw-only params in a dataclass.
    #  We don't want to do anything with this hint/field. It's not real.
    hints = {f: t for f, t in hints.items() if t is not compat.KW_ONLY}
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
            ref = compat.ForwardRef(annotation)
            try:
                annotation = compat.evaluate_forwardref(ref, globalns or None, None)
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
            if not isinstance(value, compat.ForwardRef):
                if sys.version_info >= (3, 9, 8) and sys.version_info[:3] != (3, 10, 0):
                    value = compat.ForwardRef(  # type: ignore
                        value,
                        is_argument=False,
                        is_class=inspect.isclass(annotation),
                    )
                elif sys.version_info >= (3, 7):
                    value = compat.ForwardRef(value, is_argument=False)
                else:
                    value = compat.ForwardRef(value)
        try:
            caller = getcaller()
            globalns, localns = caller.f_globals, caller.f_locals
            value = compat.evaluate_forwardref(
                value, globalns={**globalns, **base_globals}, localns=localns
            )
        except NameError:
            # this is ok, we deal with it later.
            pass
        except TypeError as e:
            warnings.warn(f"Couldn't evaluate type {value!r}: {e}", stacklevel=3)
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


cached_type_hints = compat.lru_cache(maxsize=None)(get_type_hints)


@compat.lru_cache(maxsize=None)
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


_DYNAMIC_ATTRIBUTES = (compat.SQLAMetaData, compat.sqla_registry)
cached_simple_attributes = compat.lru_cache(maxsize=None)(simple_attributes)


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


@compat.lru_cache(maxsize=None)
def safe_get_params(obj: Type) -> Mapping[str, inspect.Parameter]:
    params: Mapping[str, inspect.Parameter]
    try:
        if checks.issubclass(obj, Mapping) and not checks.istypeddict(obj):
            return {}
        params = cached_signature(obj).parameters
    except (ValueError, TypeError):  # pragma: nocover
        params = {}
    return params


@compat.lru_cache(maxsize=None)
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
                and not checks.isdescriptor(v)
                and checks.ishashable(v)
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


@classes.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True)
class TaggedUnion:
    tag: str
    types: Tuple[Type, ...]
    isliteral: bool
    types_by_values: Tuple[Tuple[Any, Type], ...]


@compat.lru_cache(maxsize=None)
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


def getcaller(frame: types.FrameType = None) -> types.FrameType:
    """Get the caller of the current scope, excluding this library.

    If `frame` is not provided, this function will use the current frame.
    """
    if frame is None:
        frame = inspect.currentframe()

    while frame.f_back:
        frame = frame.f_back
        module = inspect.getmodule(frame)
        if module and module.__name__.startswith("typical"):
            continue

        code = frame.f_code
        if getattr(code, "co_qualname", "").startswith("typical"):
            continue
        if "typical" in code.co_filename:
            continue
        return frame

    return frame


@compat.lru_cache(maxsize=None)
def get_type_graph(t: Type) -> typing.Deque[typing.Deque[TypeGraph]]:
    """Get a directed graph of the type(s) this annotation represents,

    Optimized for Breadth-First Search.

    Args:
        t: A type annotation.

    Returns:
        A 2-dimensional array of :py:class:`TypeGraph`, enabling BFS.
    """
    graph = _node(t)
    visited = {graph.type: graph}
    stack = collections.deque([graph])
    levels = collections.deque([stack.copy()])
    while stack:
        parent = stack.popleft()
        level: Deque[TypeGraph] = collections.deque()
        for var, type in _level(parent):
            seen = visited.get(type)
            is_subscripted = checks.issubscriptedgeneric(type)
            is_stdlib = checks.isstdlibtype(type)
            is_noop = type in (constants.empty, typing.Any)
            # An un-subscripted generic or stdlib type, or a non-type, cannot be cyclic.
            can_be_cyclic = is_subscripted or (is_noop, is_stdlib) == (False, False)
            if seen:
                seen.cyclic = can_be_cyclic
                node = dataclasses.replace(
                    seen, cyclic=can_be_cyclic, parent=parent, var=var
                )
                parent.nodes.append(node)
                level.append(node)
                continue

            node = _node(type, var=var, parent=parent)
            level.append(node)
            stack.append(node)
            visited[node.type] = node
        if level:
            levels.append(level)

    return levels


def itertypes(
    t: Any,
    *,
    from_root: bool = False,
    from_left: bool = False,
) -> Iterable[TypeGraph]:
    """Iterate through an annotation's type graph using Breadth-First Search.

    By default, we iterate from the bottom-right to the top-left (LIFO[LIFO[...]]).

    Args:
        t: The type annotation to traverse.
        from_root: If True, iterate though the first dimension as a stack (FIFO).
        from_left: If True, iterate through the second dimension as a stack (FIFO).
    """
    array = get_type_graph(t)
    dim_one = array.copy()
    one_pop = dim_one.popleft if from_root else dim_one.pop
    one_append = dim_one.appendleft
    two_pop = (
        operator.methodcaller("popleft") if from_left else operator.methodcaller("pop")
    )
    seen: set[TypeGraph] = set()
    seen_add = seen.add
    is_seen_items = seen.issuperset
    sent: set[TypeGraph] = set()
    sent_add = sent.add
    # Iterate through first dimension of the 2-d array representing our type graph.
    while dim_one:
        dim_two = one_pop().copy()
        deferred: Deque[TypeGraph] = collections.deque()
        deferred_append = deferred.appendleft
        # Iterate through the second dimension of the 2-d array.
        while dim_two:
            t = two_pop(dim_two)
            if t in sent:
                continue

            is_seen = t in seen
            has_children = len(t.nodes) > 0
            is_children_seen = is_seen_items(t.nodes)
            seen_add(t)
            # If we have child nodes that have not been previously seen,
            #   and the type itself has not been seen before,
            #   defer yielding this type.
            # Indicates this type is not complete
            #   (we need to know all the child types first).
            if (is_seen, is_children_seen, has_children) in (
                (False, False, False),
                (False, False, True),
            ):
                deferred_append(t)
                continue
            # Seen, but have not seen all its children,
            #   Or seen and have seen all its children,
            #   Or seen, but has no children
            # Indicates this type is not complete,
            #   or this is a repeat, so ignore it.
            if (is_seen, is_children_seen, has_children) in (
                (True, False, False),
                (True, False, True),
                (True, True, False),
            ):
                continue

            sent_add(t)
            yield t
        # Add any deferred types to the top of the stack.
        if deferred:
            one_append(deferred)


_T = TypeVar("_T")


def _node(t: type, *, var: str = None, parent: TypeGraph = None) -> TypeGraph:
    o = origin(t)
    node = TypeGraph(t, o, var=var, parent=parent)
    if parent:
        parent.nodes.append(node)
    return node


def _level(node: TypeGraph) -> Sequence[tuple[str | None, type]]:
    args = get_args(node.type)
    # Only pull annotations from the signature if this is a user-defined type.
    is_structured = checks.isstructuredtype(node.type)
    members = get_type_hints(node.type, exhaustive=is_structured)
    return [*((None, t) for t in args), *(members.items())]  # type: ignore


@classes.slotted(dict=False, weakref=True)
@dataclasses.dataclass(unsafe_hash=True)
class TypeGraph:
    """A graph representation of a type and all its subtypes.

    Enables depth-first search of the graph.
    """

    type: Type
    origin: Type
    cyclic: bool = False
    nodes: list[TypeGraph] = dataclasses.field(
        default_factory=list, hash=False, compare=False
    )
    parent: TypeGraph | None = dataclasses.field(
        default=None, hash=False, compare=False
    )
    var: str | None = dataclasses.field(default=None, hash=False, compare=False)
    _type_name: str = dataclasses.field(
        repr=False, init=False, hash=False, compare=False
    )
    _origin_name: str = dataclasses.field(
        repr=False, init=False, hash=False, compare=False
    )

    def __post_init__(self):
        self._type_name = get_qualname(self.type)
        self._origin_name = get_qualname(self.origin)

    @property
    def pretty_name(self) -> str:
        pre = ""
        if self.var:
            pre = f"{self.var}: "
        tname = self._type_name
        if self._origin_name != tname:
            tname = f"{tname} ({self._origin_name})"
        return pre + tname

    @reprlib.recursive_repr()
    def __repr__(self) -> str:
        cyclic = self.cyclic
        nodes = f"({', '.join(repr(n) for n in self.nodes)},)"
        return (
            f"<{self.__class__.__name__} "
            f"type={self._type_name}, "
            f"origin={self._origin_name}, {cyclic=}, "
            f"parent={self.parent}, "
            f"nodes={nodes}>"
        )
