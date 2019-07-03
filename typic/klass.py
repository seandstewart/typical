#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
from typing import Type

from .typed import __setattr_coerced__, _get_setter, typed_callable, annotations


def make_typedclass(
    cls: Type,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
):
    # Make the base dataclass.
    dcls = dataclasses.dataclass(
        cls,
        init=init,
        repr=repr,
        eq=eq,
        order=order,
        unsafe_hash=unsafe_hash,
        frozen=frozen,
    )
    ddict = dict(dcls.__dict__)
    ddict.pop("__dict__", None)
    ddict.pop("__weakref__", None)
    bases = (dcls,) + dcls.__bases__
    tcls = type(dcls.__name__, bases, ddict)
    tcls.__qualname__ = cls.__qualname__
    # Resolve the annotations.
    annotations(tcls)
    # Frozen dataclasses don't use the native setattr
    # So we wrap the init. This should be fine, but is more expensive.
    if frozen:
        tcls.__init__ = typed_callable(tcls.__init__)
    else:
        tcls.__setattr_original__ = _get_setter(tcls, bases)
        tcls.__setattr__ = __setattr_coerced__
    return tcls


def klass(
    _cls: Type = None,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
):
    def typedclass_wrapper(cls_):
        return make_typedclass(
            cls=cls_,
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
        )

    return typedclass_wrapper(_cls) if _cls else typedclass_wrapper
