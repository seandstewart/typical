from __future__ import annotations

import dataclasses
import functools
import sys
import warnings
from typing import Any, Iterable, MutableSet, Type, Union

def slotted(
    _cls: Type = None,
    *,
    dict: bool = False,
    weakref: bool = True,
):
    """Decorator to create a "slotted" version of the provided class.

    Returns new class object as it's not possible to add __slots__ after class creation.

    Source: https://github.com/starhel/dataslots/blob/master/src/dataslots/__init__.py
    """

    def _slots_setstate(self, state):
        for param_dict in filter(None, state):
            for slot, value in param_dict.items():
                object.__setattr__(self, slot, value)

    def wrap(cls):
        key = repr(cls)
        if key in _stack:
            raise TypeError(
                f"{cls!r} uses a custom metaclass {cls.__class__!r} "
                "which is not compatible with automatic slots. "
                "See Issue #104 on GitHub for more information."
            ) from None

        _stack.add(key)

        if sys.version_info >= (3, 10) and "typical" not in cls.__module__:
            warnings.warn(
                f"You are using Python {sys.version}. "
                "Python 3.10 introduced native support for slotted dataclasses. "
                "This is the preferred method for adding slots."
            )

        cls_dict = {**cls.__dict__}
        # Create only missing slots
        inherited_slots = set().union(
            *(getattr(c, "__slots__", set()) for c in cls.mro())
        )

        field_names = {f.name for f in dataclasses.fields(cls)}
        if dict:
            field_names.add("__dict__")
        if weakref:
            field_names.add("__weakref__")
        cls_dict["__slots__"] = (*(field_names - inherited_slots),)

        # Erase filed names from class __dict__
        for f in field_names:
            cls_dict.pop(f, None)

        # Erase __dict__ and __weakref__
        cls_dict.pop("__dict__", None)
        cls_dict.pop("__weakref__", None)

        # Pickle fix for frozen dataclass as mentioned in https://bugs.python.org/issue36424
        # Use only if __getstate__ and __setstate__ are not declared and frozen=True
        if (
            all(param not in cls_dict for param in ["__getstate__", "__setstate__"])
            and cls.__dataclass_params__.frozen
        ):
            cls_dict["__setstate__"] = _slots_setstate

        # Prepare new class with slots
        new_cls = cls.__class__(cls.__name__, cls.__bases__, cls_dict)
        new_cls.__qualname__ = cls.__qualname__
        new_cls.__module__ = cls.__module__

        _stack.clear()
        return new_cls

    return wrap if _cls is None else wrap(_cls)


_stack: MutableSet[Type] = set()


class joinedrepr(str):
    __slots__ = ("fields", "__dict__")
    fields: Iterable[Any]

    def __new__(cls, *fields):
        n = str.__new__(cls)
        n.fields = fields
        return n

    @functools.cached_property
    def __repr(self) -> str:
        return ".".join(str(f) for f in self.fields)

    def __repr__(self) -> str:
        return self.__repr

    def __str__(self) -> str:
        return self.__repr


class collectionrepr(str):
    __slots__ = (
        "root_name",
        "keys",
        "__dict__",
    )
    root_name: str
    keys: Iterable[Any]

    def __new__(cls, root_name: "ReprT", *keys):
        n = str.__new__(cls)
        n.root_name = root_name
        n.keys = keys
        return n

    @functools.cached_property
    def __repr(self) -> str:
        keys = "".join(f"[{o!r}]" for o in self.keys)
        return f"{self.root_name}{keys}"

    def __repr__(self) -> str:
        return self.__repr

    def __str__(self) -> str:
        return self.__repr


ReprT = Union[str, joinedrepr, collectionrepr]
