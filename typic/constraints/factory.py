#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
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
    Hashable,
    cast,
)

from typic.checks import (
    isoptionaltype,
    isbuiltintype,
    isconstrained,
    issubclass,
    istypeddict,
    isbuiltinsubtype,
    isnamedtuple,
    should_unwrap,
)
from typic.types import dsn, email, frozendict, path, secret, url
from typic.util import (
    origin,
    get_args,
    cached_signature,
    cached_type_hints,
    get_name,
    TypeMap,
)
from .array import (
    Array,
    FrozenSetConstraints,
    ListContraints,
    SetContraints,
    TupleContraints,
)
from .common import MultiConstraints, TypeConstraints, EnumConstraints, VT
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


ConstraintsT = Union[
    BytesConstraints,
    DecimalContraints,
    DictConstraints,
    EnumConstraints,
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

_ARRAY_CONSTRAINTS_BY_TYPE = TypeMap(
    {
        set: SetContraints,
        list: ListContraints,
        tuple: TupleContraints,
        frozenset: FrozenSetConstraints,
    }
)
ArrayConstraintsT = Union[
    SetContraints, ListContraints, TupleContraints, FrozenSetConstraints
]


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


def _from_array_type(
    t: Type[Array], *, nullable: bool = False, name: str = None
) -> ArrayConstraintsT:
    args = get_args(t)
    constr_class = cast(
        Type[ArrayConstraintsT], _ARRAY_CONSTRAINTS_BY_TYPE.get_by_parent(origin(t))
    )
    # If we don't have args, then return a naive constraint
    if not args:
        return constr_class(nullable=nullable, name=name)
    items = _resolve_args(*args, nullable=nullable)

    return constr_class(nullable=nullable, values=items, name=name)


def _from_mapping_type(
    t: Type[Mapping], *, nullable: bool = False, name: str = None
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
    key_items, value_items = _resolve_args(key_arg), _resolve_args(value_arg)
    return constr_class(
        keys=key_items, values=value_items, nullable=nullable, name=name
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
    t: Type[SimpleT], *, nullable: bool = False, name: str = None
) -> SimpleConstraintsT:
    constr_class = cast(
        Type[SimpleConstraintsT], _SIMPLE_CONSTRAINTS.get_by_parent(origin(t))
    )
    return constr_class(nullable=nullable, name=name)


def _resolve_params(**param: inspect.Parameter,) -> Mapping[str, ConstraintsT]:
    items: Dict[str, ConstraintsT] = {}

    while param:
        name, p = param.popitem()
        anno = p.annotation
        nullable = p.default in (None, Ellipsis) or isoptionaltype(anno)
        if anno in {Any, Ellipsis, p.empty}:
            continue
        if origin(anno) is Union:
            items[name] = _from_union(anno, nullable=nullable, name=name)
            continue
        items[name] = get_constraints(anno, nullable=nullable, name=name)
    return items


def _from_strict_type(
    t: Type[VT], *, nullable: bool = False, name: str = None
) -> TypeConstraints:
    return TypeConstraints(t, nullable=nullable, name=name)


def _from_enum_type(
    t: Type[enum.Enum], *, nullable: bool = False, name: str = None
) -> EnumConstraints:
    return EnumConstraints(t, nullable=nullable, name=name)


def _from_union(
    t: Type[VT], *, nullable: bool = False, name: str = None
) -> ConstraintsT:
    _nullable: bool = isoptionaltype(t)
    nullable = nullable or _nullable
    _args = get_args(t)[:-1] if _nullable else get_args(t)
    if len(_args) == 1:
        return get_constraints(_args[0], nullable=nullable, name=name)
    return MultiConstraints(
        (
            *(
                get_constraints(a, nullable=nullable)  # type: ignore
                for a in _args
            ),
        ),
        name=name,
    )


def _from_class(
    t: Type[VT], *, nullable: bool = False, name: str = None
) -> Union[ObjectConstraints, TypeConstraints, MappingConstraints]:
    if not istypeddict(t) and not isnamedtuple(t) and isbuiltinsubtype(t):
        return _from_strict_type(t, nullable=nullable, name=name)
    try:
        params: Dict[str, inspect.Parameter] = {**cached_signature(t).parameters}
        hints = cached_type_hints(t)
        for x in hints.keys() & params.keys():
            p = params[x]
            params[x] = inspect.Parameter(
                p.name, p.kind, default=p.default, annotation=hints[x]
            )
    except (ValueError, TypeError):
        return _from_strict_type(t, nullable=nullable, name=name)
    name = name or get_name(t)
    items: Optional[
        frozendict.FrozenDict[Hashable, ConstraintsT]
    ] = frozendict.FrozenDict(_resolve_params(**params)) or None
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
    return cls(**kwargs)  # type: ignore


_CONSTRAINT_BUILDER_HANDLERS = TypeMap(
    {
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
    }
)


@functools.lru_cache(maxsize=None)
def get_constraints(
    t: Type[VT], *, nullable: bool = False, name: str = None
) -> ConstraintsT:
    while should_unwrap(t):
        nullable = nullable or isoptionaltype(t)
        t = get_args(t)[0]
    if isconstrained(t):
        c: ConstraintsT = t.__constraints__  # type: ignore
        if (c.name, c.nullable) != (name, nullable):
            return dataclasses.replace(c, name=name, nullable=nullable)
        return c
    if issubclass(t, enum.Enum):
        return _from_enum_type(t, nullable=nullable, name=name)  # type: ignore
    if isnamedtuple(t) or istypeddict(t):
        handler = _from_class
    else:
        handler = _CONSTRAINT_BUILDER_HANDLERS.get_by_parent(origin(t), _from_class)  # type: ignore
    c = handler(t, nullable=nullable, name=name)  # type: ignore
    return c
