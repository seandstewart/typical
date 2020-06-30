#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# flake8: noqa
import sys
from typing import TYPE_CHECKING, Any

try:
    from typing import Final, TypedDict  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Final, TypedDict  # type: ignore
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
            def _eval_type(self, globalns: Any, localns: Any) -> Any:
                pass

    else:
        from typing import _ForwardRef as ForwardRef

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return type_._eval_type(globalns, localns)


else:  # pragma: nocover
    from typing import ForwardRef  # type: ignore

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return type_._evaluate(globalns, localns)
