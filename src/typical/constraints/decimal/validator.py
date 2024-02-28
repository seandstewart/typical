from __future__ import annotations

import functools

from typical.constraints.core import validators
from typical.constraints.core.structs import DecimalConstraints
from typical.constraints.decimal import assertions


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: DecimalConstraints,
    *,
    return_if_instance: bool,
    nullable: bool,
) -> validators.AbstractValidator:
    assertion_clss = assertions.get_assertion_cls(
        has_min=constraints.min is not None,
        has_max=constraints.max is not None,
        inclusive_min=constraints.inclusive_min,
        inclusive_max=constraints.inclusive_max,
        has_mul=constraints.mul is not None,
        has_max_digits=constraints.max_digits is not None,
        has_max_decimals=constraints.decimal_places is not None,
    )
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=assertion_clss is not None,
    )
    assertion = None
    if assertion_clss:
        d_assertion_cls, n_assertion_cls = assertion_clss
        n_assertion = n_assertion_cls(
            min=constraints.min,
            max=constraints.max,
            mul=constraints.mul,
        )
        assertion = d_assertion_cls(
            number_assertions=n_assertion,  # type: ignore[arg-type]
            max_digits=constraints.max_digits,
            max_decimal_places=constraints.decimal_places,
        )
    precheck = validators.NoOpPrecheck()
    validator = validator_cls(
        type=constraints.type,
        precheck=precheck,
        assertion=assertion,
    )
    return validator
