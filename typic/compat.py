# flake8: noqa
# pragma: nocover
from __future__ import annotations

import sys
from typing import (
    TYPE_CHECKING,
    Any,
    _SpecialForm as SpecialForm,  # type: ignore
    TypeVar,
    Optional,
    Callable,
)

try:
    from typing import Final, TypedDict, Literal, Protocol, Generic, TypeGuard, get_origin, get_args  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Final, TypedDict, Literal, Protocol, Generic, TypeGuard, get_origin, get_args  # type: ignore
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
    from asyncpg import Record
except (ImportError, ModuleNotFoundError):
    Record = dict


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
