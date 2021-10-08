from __future__ import annotations

import collections
import dataclasses
import enum
import inspect
import datetime
import ipaddress
import pathlib
import re
import uuid
from collections import deque, abc
from decimal import Decimal
from typing import (
    Mapping,
    Type,
    Union,
    Optional,
    List,
    Any,
    Dict,
    Hashable,
    cast,
    Set,
    ClassVar,
    Deque,
    Tuple,
)

from typic.checks import (
    isuniontype,
    isoptionaltype,
    isbuiltintype,
    isconstrained,
    isforwardref,
    istypeddict,
    isbuiltinsubtype,
    isnamedtuple,
    should_unwrap,
    isclassvartype,
    isenumtype,
    isabstract,
)
from typic.compat import Literal, lru_cache, UnionType
from typic.types import dsn, email, frozendict, path, secret, url
from typic.util import (
    origin,
    get_args,
    get_tag_for_types,
    cached_signature,
    cached_type_hints,
    get_name,
    TypeMap,
    empty,
)
from .array import (
    Array,
    FrozenSetConstraints,
    ListConstraints,
    SetContraints,
    TupleConstraints,
    DequeConstraints,
)
from .common import (
    MultiConstraints,
    TypeConstraints,
    EnumConstraints,
    VT,
    ConstraintsProtocolT,
    DelayedConstraints,
    ForwardDelayedConstraints,
    LiteralConstraints,
)
from .mapping import (
    MappingConstraints,
    DictConstraints,
    ObjectConstraints,
    TypedDictConstraints,
)
from .number import (
    IntContraints,
    FloatContraints,
    DecimalContraints,
    NumberT,
)
from .text import BytesConstraints, StrConstraints


@lru_cache(maxsize=None)
def get_constraints(
    t: Type[VT],
    *,
    nullable: bool = False,
    name: str = None,
    cls: Optional[Type] = ...,  # type: ignore
) -> ConstraintsProtocolT[VT]:
    while should_unwrap(t):
        nullable = nullable or isoptionaltype(t)
        t = get_args(t)[0]
    if t is cls or t in __stack:
        dc = DelayedConstraints(
            t, nullable=nullable, name=name, factory=get_constraints
        )
        return cast(ConstraintsProtocolT, dc)
    if isforwardref(t):
        if cls is ...:  # pragma: nocover
            raise TypeError(
                f"Cannot build constraints for {t} without an enclosing class."
            )
        fdc = ForwardDelayedConstraints(
            t,  # type: ignore
            cls.__module__,
            localns=getattr(cls, "__dict__", {}).copy(),
            nullable=nullable,
            name=name,
            factory=get_constraints,
        )
        return cast(ConstraintsProtocolT, fdc)
    if isconstrained(t):
        c: ConstraintsProtocolT = t.__constraints__  # type: ignore
        if (c.name, c.nullable) != (name, nullable):
            return dataclasses.replace(c, name=name, nullable=nullable)
        return c
    if isenumtype(t):
        ec = _from_enum_type(t, nullable=nullable, name=name)  # type: ignore
        return cast(ConstraintsProtocolT, ec)
    if isabstract(t):
        return cast(
            ConstraintsProtocolT, _from_strict_type(t, nullable=nullable, name=name)
        )
    if isnamedtuple(t) or istypeddict(t):
        handler = _from_class
    else:
        ot = origin(t)
        if ot in {type, abc.Callable}:
            handler = _from_strict_type  # type: ignore
            t = ot
        else:
            handler = _CONSTRAINT_BUILDER_HANDLERS.get_by_parent(ot, _from_class)  # type: ignore

    __stack.add(t)
    c = handler(t, nullable=nullable, name=name, cls=cls)
    __stack.clear()
    return c


__stack: Set[Type] = set()


ConstraintsT = Union[
    BytesConstraints,
    DecimalContraints,
    DelayedConstraints,
    DequeConstraints,
    DictConstraints,
    EnumConstraints,
    FloatContraints,
    ForwardDelayedConstraints,
    FrozenSetConstraints,
    IntContraints,
    ListConstraints,
    MappingConstraints,
    MultiConstraints,
    ObjectConstraints,
    SetContraints,
    StrConstraints,
    TupleConstraints,
    TypeConstraints,
]

_ARRAY_CONSTRAINTS_BY_TYPE = TypeMap(
    {
        set: SetContraints,
        list: ListConstraints,
        tuple: TupleConstraints,
        frozenset: FrozenSetConstraints,
        collections.deque: DequeConstraints,
    }
)
ArrayConstraintsT = Union[
    SetContraints,
    ListConstraints,
    TupleConstraints,
    FrozenSetConstraints,
    DequeConstraints,
]


def _resolve_args(
    *args, cls: Type = None, nullable: bool = False, multi: bool = True
) -> Optional[Union[ConstraintsProtocolT, Tuple[ConstraintsProtocolT, ...]]]:
    largs: Deque = deque(args)
    items: List[ConstraintsProtocolT] = []
    while largs:
        arg = largs.popleft()
        if arg in {Any, Ellipsis}:
            continue
        if isuniontype(arg):
            c = _from_union(arg, cls=cls, nullable=nullable)
            # just extend the outer multi constraints if that's what we're building
            if isinstance(c, MultiConstraints) and multi:
                items.extend(c.constraints)
            else:
                items.append(c)
            continue
        items.append(get_constraints(arg, cls=cls, nullable=nullable))
    if len(items) == 1:
        return items[0]
    if multi:
        return cast(ConstraintsProtocolT, MultiConstraints((*items,)))
    return (*items,)


def _from_array_type(
    t: Type[Array], *, nullable: bool = False, name: str = None, cls: Type = None
) -> ArrayConstraintsT:
    args = get_args(t)
    constr_class = cast(
        Type[ArrayConstraintsT], _ARRAY_CONSTRAINTS_BY_TYPE.get_by_parent(origin(t))
    )
    # If we don't have args, then return a naive constraint
    if not args:
        return constr_class(nullable=nullable, name=name)

    if constr_class is TupleConstraints and ... not in args:
        items = _resolve_args(*args, cls=cls, nullable=nullable, multi=False)
        return constr_class(nullable=nullable, values=items, name=name)  # type: ignore

    items = _resolve_args(*args, cls=cls, nullable=nullable, multi=True)
    return constr_class(nullable=nullable, values=items, name=name)  # type: ignore


def _from_mapping_type(
    t: Type[Mapping], *, nullable: bool = False, name: str = None, cls: Type = None
) -> Union[MappingConstraints, DictConstraints]:
    if isbuiltintype(t):
        return DictConstraints(nullable=nullable, name=name)
    base = getattr(t, "__origin__", t)
    constr_class: Union[Type[MappingConstraints], Type[DictConstraints]]
    constr_class = MappingConstraints
    if base is dict:
        constr_class = DictConstraints
    args = get_args(t)
    if not args:
        return constr_class(nullable=nullable, name=name)
    key_arg, value_arg = args
    key_items, value_items = (
        _resolve_args(key_arg, cls=cls),
        _resolve_args(value_arg, cls=cls),
    )
    return constr_class(
        keys=key_items, values=value_items, nullable=nullable, name=name  # type: ignore
    )


SimpleT = Union[NumberT, str, bytes]
SimpleConstraintsT = Union[
    IntContraints, FloatContraints, DecimalContraints, StrConstraints, BytesConstraints
]
_SIMPLE_CONSTRAINTS = TypeMap(
    {
        IntContraints.type: IntContraints,
        FloatContraints.type: FloatContraints,
        DecimalContraints.type: DecimalContraints,
        StrConstraints.type: StrConstraints,
        BytesConstraints.type: BytesConstraints,
    }
)


def _from_simple_type(
    t: Type[SimpleT], *, nullable: bool = False, name: str = None, cls: Type = None
) -> SimpleConstraintsT:
    constr_class = cast(
        Type[SimpleConstraintsT], _SIMPLE_CONSTRAINTS.get_by_parent(origin(t))
    )
    return constr_class(nullable=nullable, name=name)


def _resolve_params(
    cls: Type,
    **param: inspect.Parameter,
) -> Mapping[str, ConstraintsProtocolT]:
    items: Dict[str, ConstraintsProtocolT] = {}
    while param:
        name, p = param.popitem()
        anno = p.annotation
        nullable = p.default in (None, Ellipsis) or isoptionaltype(anno)
        if anno in {Any, Ellipsis, p.empty}:
            continue
        if isuniontype(anno) and not isforwardref(anno):
            items[name] = _from_union(anno, nullable=nullable, name=name, cls=cls)
            continue
        else:
            items[name] = get_constraints(anno, nullable=nullable, name=name, cls=cls)
    return items


def _from_strict_type(
    t: Type[VT], *, nullable: bool = False, name: str = None, cls: Type = None
) -> TypeConstraints:
    return TypeConstraints(t, nullable=nullable, name=name)


def _from_enum_type(
    t: Type[enum.Enum], *, nullable: bool = False, name: str = None, cls: Type = None
) -> EnumConstraints:
    return EnumConstraints(t, nullable=nullable, name=name)


def _from_literal(
    t: Type[VT], *, nullable: bool = False, name: str = None, cls: Type = None
) -> LiteralConstraints:
    return LiteralConstraints(t, nullable=nullable, name=name)


def _from_union(
    t: Type[VT], *, nullable: bool = False, name: str = None, cls: Type = None
) -> ConstraintsProtocolT:
    _nullable: bool = isoptionaltype(t)
    nullable = nullable or _nullable
    _args = get_args(t)[:-1] if _nullable else get_args(t)
    if len(_args) == 1:
        return get_constraints(_args[0], nullable=nullable, name=name, cls=cls)
    c = MultiConstraints(
        (*(get_constraints(a, nullable=nullable, cls=cls) for a in _args),),
        name=name,
        tag=get_tag_for_types(_args),
    )
    return cast(ConstraintsProtocolT, c)


def _from_class(
    t: Type[VT], *, nullable: bool = False, name: str = None, cls: Type = None
) -> ConstraintsProtocolT[VT]:
    if not istypeddict(t) and not isnamedtuple(t) and isbuiltinsubtype(t):
        return cast(
            ConstraintsProtocolT, _from_strict_type(t, nullable=nullable, name=name)
        )
    try:
        params: Dict[str, inspect.Parameter] = {**cached_signature(t).parameters}
        hints = cached_type_hints(t)
        for x in hints.keys() & params.keys():
            p = params[x]
            params[x] = inspect.Parameter(
                p.name, p.kind, default=p.default, annotation=hints[x]
            )
        for x in hints.keys() - params.keys():
            hint = hints[x]
            if not isclassvartype(hint):
                continue
            # Hack in the classvars as "parameters" to allow for validation.
            default = getattr(t, x, empty)
            args = get_args(hint)
            if not args:
                hint = ClassVar[default.__class__]  # type: ignore
            params[x] = inspect.Parameter(
                x, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=hint
            )
    except (ValueError, TypeError):
        return cast(
            ConstraintsProtocolT, _from_strict_type(t, nullable=nullable, name=name)
        )
    name = name or get_name(t)
    items: Optional[frozendict.FrozenDict[Hashable, ConstraintsT]] = (
        frozendict.FrozenDict(_resolve_params(t, **params)) or None
    )
    required = frozenset(
        (
            pname
            for pname, p in params.items()
            if (
                p.kind not in {p.VAR_POSITIONAL, p.VAR_KEYWORD} and p.default is p.empty
            )
        )
    )
    has_varargs = any(
        p.kind in {p.VAR_KEYWORD, p.VAR_POSITIONAL} for p in params.values()
    )
    kwargs = {
        "type": t,
        "nullable": nullable,
        "name": name,
        "required_keys": required,
        "items": items,
        "total": not has_varargs,
    }
    cls = ObjectConstraints
    if istypeddict(t):
        cls = TypedDictConstraints
        kwargs.update(type=dict, ttype=t, total=getattr(t, "__total__", bool(required)))
    c = cls(**kwargs)  # type: ignore
    return cast(ConstraintsProtocolT, c)


_CONSTRAINT_BUILDER_HANDLERS = TypeMap(
    {
        set: _from_array_type,
        frozenset: _from_array_type,
        list: _from_array_type,
        tuple: _from_array_type,
        collections.deque: _from_array_type,
        dict: _from_mapping_type,  # type: ignore
        int: _from_simple_type,
        float: _from_simple_type,
        Decimal: _from_simple_type,
        str: _from_simple_type,
        bytes: _from_simple_type,
        bool: _from_strict_type,
        datetime.datetime: _from_strict_type,
        datetime.date: _from_strict_type,
        datetime.time: _from_strict_type,
        url.NetworkAddress: _from_strict_type,
        url.URL: _from_strict_type,
        url.AbsoluteURL: _from_strict_type,
        url.RelativeURL: _from_strict_type,
        dsn.DSN: _from_strict_type,
        pathlib.Path: _from_strict_type,
        path.FilePath: _from_strict_type,
        path.DirectoryPath: _from_strict_type,
        path.PathType: _from_strict_type,
        url.HostName: _from_strict_type,
        email.Email: _from_strict_type,
        secret.SecretStr: _from_strict_type,
        secret.SecretBytes: _from_strict_type,
        uuid.UUID: _from_strict_type,
        re.Pattern: _from_strict_type,  # type: ignore
        ipaddress.IPv4Address: _from_strict_type,
        ipaddress.IPv6Address: _from_strict_type,
        Union: _from_union,  # type: ignore
        UnionType: _from_union,  # type: ignore
        Literal: _from_literal,  # type: ignore
    }
)
