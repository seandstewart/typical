from __future__ import annotations

import inspect
from typing import Callable, TypeVar, cast, overload

from typic import checks
from typic.compat import Protocol
from typic.core.constraints import factory

__all__ = ("constrained",)


@overload
def constrained(cls: type[T], /) -> type[factory.ConstrainedType[T]]:
    ...


@overload
def constrained(
    cls: type[T],
    /,
    *,
    keys: type | tuple[type, ...],
    values: type | tuple[type, ...],
    **constraints,
) -> factory.ConstrainedType[T]:
    ...


@overload
def constrained(
    *,
    keys: type | tuple[type, ...],
    values: type | tuple[type, ...],
    **constraints,
) -> Callable[[T], type[factory.ConstrainedType[T]]]:
    ...


@overload
def constrained(
    **constraints,
) -> Callable[[T], type[factory.ConstrainedType[T]]]:
    ...


def constrained(
    cls=None,
    *,
    keys=None,
    values=None,
    **constraints,
):
    """A wrapper to indicate a 'constrained' type.

    Parameters
    ----------
    keys
        For container-types, you can pass in other constraints for the values to be
        validated against. Can be a single constraint for all values or a tuple of
        constraints to choose from.
    values
        For container-types, you can pass in other constraints for the values to be
        validated against. Can be a single constraint for all values or a tuple of
        constraints to choose from.

    **constraints
        The restrictions to apply to values being cast as the decorated type.

    Examples
    --------
    >>> import typic
    >>>
    >>> @typic.constrained(max_length=10)
    ... class ShortStr(str):
    ...     '''A short string.'''
    ...     ...
    ...
    >>> ShortStr('foo')
    'foo'
    >>> ShortStr('waytoomanycharacters')
    Traceback (most recent call last):
    ...
    typic.constraints.error.ConstraintValueError: Given value <'waytoomanycharacters'> fails constraints: (type=str, nullable=False, max_length=10)
    >>> @typic.constrained(values=ShortStr, max_items=2)
    ... class SmallMap(dict):
    ...     '''A small map that only allows short strings.'''
    ...
    >>> import json
    >>> print(json.dumps(typic.schema(SmallMap, primitive=True), indent=2, sort_keys=True))
    {
      "additionalProperties": {
        "maxLength": 10,
        "type": "string"
      },
      "description": "A small map that only allows short strings.",
      "maxProperties": 2,
      "title": "SmallMap",
      "type": "object"
    }


    See Also
    --------
    :py:mod:`typic.constraints.array`

    :py:mod:`typic.constraints.common`

    :py:mod:`typic.constraints.error`

    :py:mod:`typic.constraints.mapping`

    :py:mod:`typic.constraints.number`

    :py:mod:`typic.constraints.text`
    """

    def constrained_wrapper(
        cls_: type[T],
    ):
        name, module = cls_.__name__, cls_.__module__
        # If we called this function on a builtin:
        #   - create a new name and for the type
        #   - walk back to the callsite to get the correct module name.
        if checks.isbuiltintype(cls_):
            name = f"Constrained{cls_.__name__.capitalize()}"
            stack = inspect.stack()
            if len(stack) > 2:
                frame = stack[2]
                mod = inspect.getmodule(frame)
                module = mod and mod.__name__ or module
        # Create the new type, inheriting from our Constraint class.
        bases = (cls_, *cls_.__bases__, factory.ConstrainedType)
        cdict = {"__module__": module}
        constrained_type = type(
            name, bases, cdict, keys=keys, values=values, **constraints
        )
        return cast(factory.ConstrainedType[T], constrained_type)

    return constrained_wrapper(cls) if cls else constrained_wrapper


T = TypeVar("T")


class _ConstrainedTypeFactory(Protocol[T]):
    def __call__(
        self,
        keys: type | tuple[type, ...] = None,
        values: type | tuple[type, ...] = None,
        **constraints,
    ) -> factory.ConstrainedType[T]:
        ...
