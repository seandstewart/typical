from __future__ import annotations

import functools

from typic.core.constraints.core import validators
from typic.core.constraints.core.types import TextConstraints
from typic.core.constraints.text import assertions, prechecks


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: TextConstraints,
    *,
    return_if_instance: bool,
    nullable: bool,
) -> validators.AbstractValidator:
    assertion_cls = assertions.get_assertion_cls(
        has_min=constraints.min_length is not None,
        has_max=constraints.max_length is not None,
        has_regex=constraints.regex is not None,
    )
    precheck_cls = (
        prechecks.get_precheck_cls(
            should_curtail_length=constraints.curtail_length is not None,
            should_strip_whitespace=constraints.strip_whitespace is not None,
        )
        or validators.NoOpPrecheck
    )
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=assertion_cls is not None,
    )
    assertion = (
        assertion_cls(
            min_length=constraints.min_length,
            max_length=constraints.max_length,
            regex=constraints.regex,
        )
        if assertion_cls
        else None
    )
    precheck = precheck_cls(max_length=constraints.curtail_length)
    validator = validator_cls(
        type=constraints.type,
        precheck=precheck,
        assertion=assertion,
    )
    return validator
