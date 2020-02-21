#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
from typing import Type

from typic.api import wrap_cls
from .serde import SerdeFlags


def make_typedclass(
    cls: Type,
    *,
    init: bool = True,
    repr: bool = True,
    eq: bool = True,
    order: bool = False,
    unsafe_hash: bool = False,
    frozen: bool = False,
    delay: bool = False,
    strict: bool = False,
    jsonschema: bool = False,
    serde: SerdeFlags = None
):
    """A convenience function for generating a dataclass with type-coercion.

    Allows the user to create typed dataclasses on-demand from a base-class, i.e.::

        TypedClass = make_typedclass(UnTypedClass)

    The preferred method is via the ``klass`` decorator, however.

    See Also
    --------
    :py:func:`klass`
    :py:func:`dataclasses.dataclass`
    """
    # Make the base dataclass.
    dcls = dataclasses.dataclass(  # type: ignore
        cls,
        init=init,
        repr=repr,
        eq=eq,
        order=order,
        unsafe_hash=unsafe_hash,
        frozen=frozen,
    )
    return wrap_cls(
        dcls,
        delay=delay,
        strict=strict,
        jsonschema=jsonschema,
        serde=serde or SerdeFlags(),
    )


def klass(
    _cls: Type = None,
    *,
    init: bool = True,
    repr: bool = True,
    eq: bool = True,
    order: bool = False,
    unsafe_hash: bool = False,
    frozen: bool = False,
    delay: bool = False,
    strict: bool = False,
    jsonschema: bool = True,
    serde: SerdeFlags = None
):
    """A convenience decorator for generating a dataclass with type-coercion.

    This::

        import typic

        @typic.klass
        class Foo:
            bar: str

    Is functionally equivalent to::

        import dataclasses
        import typic

        @typic.al
        @dataclasses.dataclass
        class Foo:
            bar: str

    See Also
    --------
    :py:func:`~typic.api.wrap_cls`
    :py:func:`dataclasses.dataclass`
    """

    def typedclass_wrapper(cls_):
        return make_typedclass(
            cls=cls_,
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            delay=delay,
            strict=strict,
            jsonschema=jsonschema,
            serde=serde,
        )

    return typedclass_wrapper(_cls) if _cls else typedclass_wrapper
