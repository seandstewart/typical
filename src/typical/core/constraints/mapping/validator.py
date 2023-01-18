from __future__ import annotations

import functools
from typing import cast

from typical.core.annotations import TrueOrFalseT
from typical.core.constraints.core import types, validators
from typical.core.constraints.mapping import assertions

__all__ = ("get_validator",)


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: types.MappingConstraints,
    *,
    return_if_instance: TrueOrFalseT,
    nullable: TrueOrFalseT,
) -> validators.AbstractValidator:
    assertion_cls = assertions.get_assertion_cls(
        has_min=constraints.min_items is not None,
        has_max=constraints.max_items is not None,
        has_key_pattern=constraints.key_pattern is not None,
    )
    precheck_cls = validators.NoOpPrecheck
    has_assertion = cast(TrueOrFalseT, assertion_cls is not None)
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=has_assertion,
    )
    assertion = (
        assertion_cls(
            min_items=constraints.min_items,
            max_items=constraints.max_items,
            key_pattern=constraints.key_pattern,
        )
        if assertion_cls
        else None
    )
    precheck = precheck_cls(type=constraints.type)
    validator = validator_cls(
        type=constraints.type,
        precheck=precheck,
        assertion=assertion,
    )
    return validator
