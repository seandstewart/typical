from __future__ import annotations

import functools

from typic.core.constraints.core import validators
from typic.core.constraints.core.types import NumberConstraints
from typic.core.constraints.number import assertions


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: NumberConstraints,
    *,
    return_if_instance: bool,
    nullable: bool,
) -> validators.AbstractValidator:
    assertion_cls = assertions.get_assertion_cls(
        has_min=constraints.min is not None,
        inclusive_min=constraints.inclusive_min,
        has_max=constraints.max is not None,
        inclusive_max=constraints.inclusive_max,
        has_mul=constraints.mul is not None,
    )
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=assertion_cls is not None,
    )
    assertion = (
        assertion_cls(
            min=constraints.min,
            max=constraints.max,
            mul=constraints.mul,
        )
        if assertion_cls
        else None
    )
    precheck = validators.NoOpPrecheck()
    validator = validator_cls(
        type=constraints.type,
        precheck=precheck,
        assertion=assertion,
    )
    return validator
