# flake8: noqa
# pragma: nocover
from __future__ import annotations

import ast
import sys
import types
from datetime import date, datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    ForwardRef,
    Generic,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

PYTHON_VERSION = sys.version_info

if PYTHON_VERSION >= (3, 11):
    from typing import ParamSpec, Self
else:
    from typing_extensions import ParamSpec, Self  # type: ignore[assignment]

if PYTHON_VERSION >= (3, 10):
    from typing import TypeGuard

    DATACLASS_KW_ONLY = DATACLASS_MATCH_ARGS = DATACLASS_NATIVE_SLOTS = True

    def transform_annotation(annotation: str) -> str:
        return annotation

else:
    from typing_extensions import TypeGuard

    DATACLASS_KW_ONLY = DATACLASS_MATCH_ARGS = DATACLASS_NATIVE_SLOTS = False

    from typical.core.future import transform_annotation


if TYPE_CHECKING:
    eval_type: Callable[..., Any]
    SpecialForm: type

    class SQLAMetaData: ...

    class sqla_registry: ...

    class Record: ...

    asyncpg = types.ModuleType("asyncpg")

    class _KWOnlyType:
        pass

    KW_ONLY = _KWOnlyType()

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any: ...

    F = TypeVar("F", bound=Callable)

    def lru_cache(
        maxsize: Optional[int] = 128, typed: bool = False
    ) -> Callable[[F], F]: ...

    def unparse(ast_obj: ast.AST) -> str: ...

else:
    from functools import lru_cache
    from typing import _eval_type as eval_type
    from typing import _SpecialForm as SpecialForm

    class _KWOnlyType: ...

    KW_ONLY = _KWOnlyType()

    UnionType = Union

    if PYTHON_VERSION >= (3, 10):
        from dataclasses import KW_ONLY
        from types import UnionType

        def evaluate_forwardref(
            type_: ForwardRef,
            globalns: Any,
            localns: Any,
            recursive_guard: set = None,
        ) -> Any:
            if type(type_) is not ForwardRef:
                return type_
            recursive_guard = recursive_guard or set()
            return type_._evaluate(globalns, localns, recursive_guard)

    elif PYTHON_VERSION >= (3, 9):
        from ast import unparse

        def evaluate_forwardref(
            type_: ForwardRef,
            globalns: Any,
            localns: Any,
            recursive_guard: set = None,
        ) -> Any:
            if type(type_) is not ForwardRef:
                return type_
            arg = transform_annotation(type_.__forward_arg__)
            globalns = {**globals(), **globalns}
            type_ = ForwardRef(arg, is_argument=type_.__forward_is_argument__)
            recursive_guard = recursive_guard or set()
            return type_._evaluate(globalns, localns, recursive_guard)

    else:  # pragma: nocover
        from astunparse import unparse

        def evaluate_forwardref(
            type_: ForwardRef,
            globalns: Any,
            localns: Any,
            recursive_guard: set = None,
        ) -> Any:
            if type(type_) is not ForwardRef:
                return type_
            arg = transform_annotation(type_.__forward_arg__)
            ntype_ = ForwardRef(arg, is_argument=type_.__forward_is_argument__)
            return ntype_._evaluate({**globals(), **globalns}, localns)

    try:
        from sqlalchemy import MetaData as SQLAMetaData
    except ImportError:

        class SQLAMetaData: ...

    try:
        from sqlalchemy.orm import registry as sqla_registry
    except ImportError:

        class sqla_registry: ...

    try:
        import asyncpg

        Record = asyncpg.Record

        def _patch_asyncpg_range():
            # N.B.: Some hacking ahead.
            # asyncpg's builtin Range object has some limitations which make ser/des finnicky.
            #   It takes the parameter `empty`, but exposes that value as the property
            #   `isempty`, hides all its attributes behind properties, and has no annotations.
            #
            # I'd rather just update the db client to return our own type for pg Ranges, but that
            #   would require writing a custom encoder/decoder for postgres :(
            #   See: https://magicstack.github.io/asyncpg/current/usage.html#custom-type-conversions
            #
            # Instead, I'm just flagging to typical that we should use `isempty` as the value for
            #   `empty` when we serialize a range to JSON, etc.

            asyncpg.Range.__serde_flags__ = dict(
                # Don't try to get the attribute `empty`.
                exclude=("empty",),
                # Alias `isempty` to `empty` when serializing.
                fields={"isempty": "empty"},
            )
            # We're also adding in annotations so we preserve these fields when serializing.
            asyncpg.Range.__annotations__ = {
                "lower": Union[int, date, datetime, None],
                "upper": Union[int, date, datetime, None],
                "lower_inc": bool,
                "upper_inc": bool,
                "isempty": bool,
            }

        _patch_asyncpg_range()

    except (ImportError, ModuleNotFoundError):
        Record = dict
        asyncpg = types.ModuleType("asyncpg")
        asyncpg.Record = Record


__all__ = (
    "DATACLASS_KW_ONLY",
    "DATACLASS_MATCH_ARGS",
    "DATACLASS_NATIVE_SLOTS",
    "eval_type",
    "evaluate_forwardref",
    "Final",
    "ForwardRef",
    "Generic",
    "KW_ONLY",
    "Literal",
    "lru_cache",
    "Protocol",
    "Record",
    "sqla_registry",
    "SQLAMetaData",
    "TypedDict",
    "TypeGuard",
    "UnionType",
    "transform_annotation",
)
