#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import enum
import functools
import inspect
import datetime
import ipaddress
import pathlib
import re
import uuid
from decimal import Decimal
from typing import (
    Mapping,
    Type,
    Union,
    Optional,
    List,
    Any,
    Dict,
    Callable,
    Hashable,
)

from typic.checks import (
    isoptionaltype,
    isbuiltintype,
    isconstrained,
    issubclass,
    istypeddict,
)
from typic.types import dsn, email, frozendict, path, secret, url
from typic.util import origin, get_args, cached_signature, cached_type_hints
from .array import (
    Array,
    FrozenSetConstraints,
    ListContraints,
    SetContraints,
    TupleContraints,
)
from .common import MultiConstraints, TypeConstraints, VT
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
    Number,
)
from .text import BytesConstraints, StrConstraints


ConstraintsT = Union[
    BytesConstraints,
    DecimalContraints,
    DictConstraints,
    FloatContraints,
    FrozenSetConstraints,
    IntContraints,
    ListContraints,
    MappingConstraints,
    MultiConstraints,
    ObjectConstraints,
    SetContraints,
    StrConstraints,
    TupleContraints,
    TypeConstraints,
]

_ARRAY_CONSTRAINTS_BY_TYPE: Mapping[
    Type[Array],
    Type[Union[SetContraints, ListContraints, TupleContraints, FrozenSetConstraints]],
] = {
    set: SetContraints,
    list: ListContraints,
    tuple: TupleContraints,
    frozenset: FrozenSetConstraints,
}


def _resolve_args(*args, nullable: bool = False) -> Optional[ConstraintsT]:
    largs: List = [*args]
    items: List[ConstraintsT] = []

    while largs:
        arg = largs.pop()
        if arg in {Any, Ellipsis}:
            continue
        if origin(arg) is Union:
            c = _from_union(arg, nullable=nullable)
            if isinstance(c, MultiConstraints):
                items.extend(c.constraints)
            else:
                items.append(c)
            continue
        items.append(get_constraints(arg, nullable=nullable))
    if len(items) == 1:
        return items[0]
    return MultiConstraints((*items,))  # type: ignore


def _from_array_type(t: Type[Array], *, nullable: bool = False) -> ConstraintsT:
    args = get_args(t)
    constr_class = _ARRAY_CONSTRAINTS_BY_TYPE[origin(t)]
    # If we don't have args, then return a naive constraint
    if not args:
        return constr_class(nullable=nullable)
    items = _resolve_args(*args, nullable=nullable)

    return constr_class(nullable=nullable, values=items)


def _from_mapping_type(
    t: Type[Mapping], *, nullable: bool = False
) -> Union[MappingConstraints, DictConstraints]:
    if isbuiltintype(t):
        return DictConstraints(nullable=nullable)
    base = getattr(t, "__origin__", t)
    constr_class: Union[
        Type[MappingConstraints], Type[DictConstraints]
    ] = MappingConstraints
    if base is dict:
        constr_class = DictConstraints
    args = get_args(t)
    if not args:
        return constr_class(nullable=nullable)
    key_arg, value_arg = args
    key_items, value_items = _resolve_args(key_arg), _resolve_args(value_arg)
    return constr_class(keys=key_items, values=value_items, nullable=nullable)


SimpleT = Union[Number, str, bytes]
SimpleConstraintsT = Union[
    IntContraints, FloatContraints, DecimalContraints, StrConstraints, BytesConstraints
]
_SIMPLE_CONSTRAINTS: Mapping[Type[SimpleT], Type[SimpleConstraintsT]] = {
    IntContraints.type: IntContraints,
    FloatContraints.type: FloatContraints,
    DecimalContraints.type: DecimalContraints,
    StrConstraints.type: StrConstraints,
    BytesConstraints.type: BytesConstraints,
}


def _from_simple_type(
    t: Type[SimpleT], *, nullable: bool = False
) -> SimpleConstraintsT:
    constr_class = _SIMPLE_CONSTRAINTS[t]
    return constr_class(nullable=nullable)


def _resolve_params(**param: inspect.Parameter,) -> Mapping[str, ConstraintsT]:
    items: Dict[str, ConstraintsT] = {}

    while param:
        name, p = param.popitem()
        anno = p.annotation
        if anno in {Any, Ellipsis, p.empty}:
            continue
        if origin(anno) is Union:
            items[name] = _from_union(anno)
            continue
        items[name] = get_constraints(anno)
    return items


def _from_strict_type(t: Type[VT], *, nullable: bool = False) -> TypeConstraints:
    return TypeConstraints(t, nullable=nullable)


def _from_union(t: Type[VT], *, nullable: bool = False) -> ConstraintsT:
    _nullable: bool = isoptionaltype(t)
    nullable = nullable or _nullable
    _args = get_args(t)[:-1] if _nullable else get_args(t)
    if len(_args) == 1:
        return get_constraints(_args[0], nullable=nullable)
    return MultiConstraints(
        (
            *(
                get_constraints(a, nullable=nullable)  # type: ignore
                for a in _args
            ),
        )
    )


def _from_class(
    t: Type[VT], *, nullable: bool = False
) -> Union[ObjectConstraints, TypeConstraints, MappingConstraints]:
    try:
        params: Dict[str, inspect.Parameter] = {**cached_signature(t).parameters}
        hints = cached_type_hints(t)
        for x in hints.keys() & params.keys():
            p = params[x]
            params[x] = inspect.Parameter(
                p.name, p.kind, default=p.default, annotation=hints[x]
            )
    except (ValueError, TypeError):
        return _from_strict_type(t, nullable=nullable)
    items: Optional[
        frozendict.FrozenDict[Hashable, ConstraintsT]
    ] = frozendict.FrozenDict(_resolve_params(**params)) or None
    total = getattr(t, "__total__", True)
    keys = frozenset(params.keys()) if total else frozenset({})
    kwargs = dict(
        type=t, nullable=nullable, required_keys=keys, items=items, total=total
    )
    cls = ObjectConstraints
    if istypeddict(t):
        cls = TypedDictConstraints
        kwargs.update(type=dict, ttype=t)
    return cls(**kwargs)


_CONSTRAINT_BUILDER_HANDLERS: Mapping[Type[Any], Callable] = {
    set: _from_array_type,
    frozenset: _from_array_type,
    list: _from_array_type,
    tuple: _from_array_type,
    dict: _from_mapping_type,
    int: _from_simple_type,
    float: _from_simple_type,
    Decimal: _from_simple_type,
    str: _from_simple_type,
    bytes: _from_simple_type,
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
}


@functools.lru_cache(maxsize=None)
def get_constraints(t: Type[VT], *, nullable: bool = False) -> ConstraintsT:
    if isconstrained(t):
        return t.__constraints__  # type: ignore
    if issubclass(t, enum.Enum):
        return _from_strict_type(t, nullable=nullable)
    handler = _CONSTRAINT_BUILDER_HANDLERS.get(origin(t)) or _from_class
    c = handler(t, nullable=nullable)
    return c
