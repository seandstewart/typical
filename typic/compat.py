#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# flake8: noqa
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
    from typing import Final, TypedDict, Literal, Protocol  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Final, TypedDict, Literal, Protocol  # type: ignore
try:
    from typing import ForwardRef  # type: ignore
except ImportError:  # pragma: nocover
    from typing import _ForwardRef as ForwardRef  # type: ignore
try:
    from sqlalchemy import MetaData as SQLAMetaData  # type: ignore
except ImportError:  # pragma: nocover

    class SQLAMetaData:  # type: ignore
        ...


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


elif sys.version_info >= (3, 9):
    from typing import ForwardRef

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any:
        recursive_guard = recursive_guard or set()
        return type_._evaluate(globalns, localns, recursive_guard)


else:  # pragma: nocover
    from typing import ForwardRef  # type: ignore

    def evaluate_forwardref(
        type_: ForwardRef,
        globalns: Any,
        localns: Any,
        recursive_guard: set = None,
    ) -> Any:
        return type_._evaluate(globalns, localns)


if TYPE_CHECKING:
    F = TypeVar("F", bound=Callable)

    def lru_cache(
        maxsize: Optional[int] = 128, typed: bool = False
    ) -> Callable[[F], F]:
        pass


else:
    from functools import lru_cache
