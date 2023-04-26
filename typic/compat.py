# flake8: noqa
# pragma: nocover
from __future__ import annotations

import sys
import types
from datetime import date, datetime
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    _SpecialForm as SpecialForm,  # type: ignore
    TypeVar,
    Optional,
    Union,
)

try:
    from typing import Final  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Final  # type: ignore
try:
    from typing import TypedDict  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import TypedDict  # type: ignore
try:
    from typing import Literal  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Literal  # type: ignore
try:
    from typing import Protocol  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Protocol  # type: ignore
try:
    from typing import Generic  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Generic  # type: ignore
try:
    from typing import TypeGuard  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import TypeGuard  # type: ignore
try:
    from typing import get_origin  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import get_origin  # type: ignore
try:
    from typing import get_args  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import get_args  # type: ignore
try:
    from typing import ForwardRef  # type: ignore
except ImportError:  # pragma: nocover
    from typing import _ForwardRef as ForwardRef  # type: ignore
try:
    from sqlalchemy import MetaData as SQLAMetaData  # type: ignore
except ImportError:  # pragma: nocover

    class SQLAMetaData:  # type: ignore
        ...


try:
    from sqlalchemy.orm import registry as sqla_registry  # type: ignore
except ImportError:  # pragma: nocover

    class sqla_registry:  # type: ignore
        ...


try:  # pragma: nocover
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


if sys.version_info < (3, 7):  # pragma: nocover
    if TYPE_CHECKING:

        class ForwardRef:
            __forward_arg__: str

            def _eval_type(self, globalns: Any, localns: Any) -> Any:
                pass

    else:
        from typing import _ForwardRef as ForwardRef

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any:
        return type_._eval_type(globalns, localns)

elif sys.version_info >= (3, 9):  # pragma: nocover
    from typing import ForwardRef

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any:
        recursive_guard = recursive_guard or set()
        return type_._evaluate(globalns, localns, recursive_guard)  # type: ignore

else:  # pragma: nocover
    from typing import ForwardRef  # type: ignore

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any:
        return type_._evaluate(globalns, localns)  # type: ignore


if TYPE_CHECKING:
    F = TypeVar("F", bound=Callable)

    def lru_cache(
        maxsize: Optional[int] = 128, typed: bool = False
    ) -> Callable[[F], F]:
        pass

else:
    from functools import lru_cache


if sys.version_info >= (3, 10):  # pragma: nocover
    DATACLASS_KW_ONLY = DATACLASS_MATCH_ARGS = DATACLASS_NATIVE_SLOTS = True
    from dataclasses import KW_ONLY  # type: ignore
    from types import UnionType

else:
    DATACLASS_KW_ONLY = DATACLASS_MATCH_ARGS = DATACLASS_NATIVE_SLOTS = False
    from typing import Union as UnionType

    class _KW_ONLY_TYPE:
        pass

    KW_ONLY = _KW_ONLY_TYPE()

__all__ = (
    "Final",
    "TypedDict",
    "Literal",
    "Protocol",
    "TypeGuard",
    "ForwardRef",
    "SQLAMetaData",
    "sqla_registry",
    "evaluate_forwardref",
    "lru_cache",
    "DATACLASS_KW_ONLY",
    "DATACLASS_MATCH_ARGS",
    "DATACLASS_NATIVE_SLOTS",
    "KW_ONLY",
)
