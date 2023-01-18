from __future__ import annotations

import functools
from typing import TypeVar

from typical.core.constraints.core import validators
from typical.core.constraints.core.types import StructuredObjectConstraints

_VT = TypeVar("_VT")


@functools.lru_cache(maxsize=None)
def get_validator(
    constraints: StructuredObjectConstraints[_VT],
    *,
    return_if_instance: bool,
    nullable: bool,
    has_fields: bool,
    is_tuple: bool,
) -> validators.AbstractValidator[_VT]:
    precheck_cls = validators.NoOpPrecheck
    validator_cls = validators.get_validator_cls(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=False,
    )
    precheck = precheck_cls(type=constraints.type)
    validator = validator_cls(
        type=constraints.origin,
        precheck=precheck,
        assertion=None,
    )
    return validator
