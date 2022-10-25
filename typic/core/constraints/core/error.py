from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typic.core.constraints.core import types


__all__ = (
    "ConstraintError",
    "ConstraintSyntaxError",
    "ConstraintTypeError",
    "ConstraintValueError",
    "ConstraintErrorReport",
)


class ConstraintError(Exception):
    """The root exception for all Constraints-related errors."""


class ConstraintSyntaxError(ConstraintError, SyntaxError):
    """A generic error indicating an improperly defined constraint."""

    pass


class ConstraintTypeError(ConstraintError, TypeError):
    """A generic error indicating an illegal set of parameters."""

    pass


class ConstraintValueError(ConstraintError, ValueError):
    """A generic error indicating a value violates a constraint."""

    def __init__(
        self,
        message: str,
        constraints: types.AbstractConstraints,
        path: str,
        **errors: Exception,
    ):
        self.path = path
        self.constraints = constraints
        self.errors = errors
        super().__init__(message)

    def dump(self) -> list[ConstraintErrorReport]:
        stack = deque(((self.path, self), *self.errors.items()))
        out: list[ConstraintErrorReport] = []
        outappend = out.append
        while stack:
            path, err = stack.popleft()
            outappend(
                {
                    "location": path,
                    "error_class": err.__class__.__name__,
                    "detail": str(err),
                }
            )
            if isinstance(err, ConstraintValueError):
                stack.extend(err.errors.items())
        return out


class ConstraintErrorReport(TypedDict):
    location: str
    error_class: str
    detail: str