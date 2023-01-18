from __future__ import annotations

import collections
import functools
from typing import TypeVar

from typical.core.constraints.array import assertions, prechecks
from typical.core.constraints.core import types, validators

_AT = TypeVar("_AT", frozenset, set, list, tuple, collections.deque)


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: types.ArrayConstraints[_AT],
    *,
    return_if_instance: bool,
    nullable: bool,
) -> validators.AbstractInstanceValidator[_AT]:
    assertion_cls = assertions.get_assertion_cls(
        has_min=constraints.min_items is not None,
        has_max=constraints.max_items is not None,
    )
    precheck_cls: type[validators.NoOpPrecheck | prechecks.UniquePrecheck]
    precheck_cls = validators.NoOpPrecheck
    if constraints.unique and not issubclass(constraints.type, (set, frozenset)):
        precheck_cls = prechecks.UniquePrecheck
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=assertion_cls is not None,
    )
    assertion = (
        assertion_cls(
            min_items=constraints.min_items,
            max_items=constraints.max_items,
        )
        if assertion_cls
        else None
    )
    precheck = precheck_cls(cls=constraints.origin)
    validator = validator_cls(
        type=constraints.type,
        precheck=precheck,
        assertion=assertion,
    )
    return validator
