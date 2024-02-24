from __future__ import annotations

import inspect
from typing import Callable, TypeVar, cast, overload

from typical import checks
from typical.compat import Protocol
from typical.constraints import factory

__all__ = ("constrained",)


@overload
def constrained(cls: type[T], /) -> type[factory.ConstrainedType[T]]: ...


@overload
def constrained(
    cls: type[T],
    /,
    *,
    keys: type | tuple[type, ...],
    values: type | tuple[type, ...],
    **constraints,
) -> factory.ConstrainedType[T]: ...


@overload
def constrained(
    *,
    keys: type | tuple[type, ...],
    values: type | tuple[type, ...],
    **constraints,
) -> Callable[[T], type[factory.ConstrainedType[T]]]: ...


@overload
def constrained(
    **constraints,
) -> Callable[[T], type[factory.ConstrainedType[T]]]: ...


def constrained(
    cls=None,
    *,
    keys=None,
    values=None,
    **constraints,
):
    """A class wrapper to declare a 'constrained' type.

    Keyword Args:
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

    Examples:
        >>> import typical
        >>>
        >>> @typical.constrained(max_length=10)
        ... class ShortStr(str):
        ...     '''A short string.'''
        ...     ...
        ...
        >>> ShortStr('foo')
        'foo'
        >>> ShortStr('waytoomanycharacters')
        Traceback (most recent call last):
        ...
        typic.core.constraints.core.error.ConstraintValueError: Given value <'waytoomanycharacters'> fails constraints: (type=ShortStr, max_length=10)
        >>> @typical.constrained(values=ShortStr, max_items=2)
        ... class SmallMap(dict):
        ...     '''A small map that only allows short strings.'''
        ...
        >>> import json
        >>> from typical.magic import schema
        >>> print(json.dumps(schema.schema(SmallMap, primitive=True), indent=2, sort_keys=True))
        {
          "additionalProperties": {
            "$ref": "#/definitions/ShortStr"
          },
          "definitions": {
            "ShortStr": {
              "maxLength": 10,
              "title": "ShortStr",
              "type": "string"
            }
          },
          "maxProperties": 2,
          "title": "ShortStrSmallMap",
          "type": "object"
        }


    See Also:
        - :py:mod:`typic.constraints.array`
        - :py:mod:`typic.constraints.common`
        - :py:mod:`typic.constraints.error`
        - :py:mod:`typic.constraints.mapping`
        - :py:mod:`typic.constraints.number`
        - :py:mod:`typic.constraints.text`
    """

    def constrained_wrapper(
        cls_: type[T],
    ):
        name, module, qualname = cls_.__name__, cls_.__module__, cls_.__qualname__
        # If we called this function on a builtin:
        #   - create a new name and for the type
        #   - walk back to the callsite to get the correct module name.
        if checks.isbuiltintype(cls_):
            # If we have a builtin, this is by definition the "parent".
            parent = cls_
            name = f"Constrained{cls_.__name__.capitalize()}"
            stack = inspect.stack()
            if len(stack) > 2:
                frame = stack[2]
                mod = inspect.getmodule(frame)
                module = mod and mod.__name__ or module
            qualname = f"{module}.{name}"
            cls_ = type(name, (parent,), {"__qualname__": qualname})
        else:
            # Otherwise, we need to determine the "parent" type to validate against
            #   in the new constructor.
            bases = cls_.__bases__
            pix = 1 if len(bases) > 1 else 0
            parent = bases[pix]
        # Create the new type, inheriting from our Constraint class.
        bases = (cls_, *cls_.__bases__, factory.ConstrainedType)
        cdict = {"__module__": module}
        constrained_type = type(
            name,
            bases,
            cdict,
            keys=keys,
            values=values,
            parent=parent,
            type_name=name,
            type_qualname=qualname,
            **constraints,
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
    ) -> factory.ConstrainedType[T]: ...
