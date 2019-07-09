#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import inspect

import pytest

import typic


def foo(arg, *args, kwd=None, **kwargs):  # pragma: nocover
    pass


def one(arg):  # pragma: nocover
    pass


def pos(arg, *args):  # pragma: nocover
    pass


def kwd(*, kwd=None):  # pragma: nocover
    pass


def kwarg(arg, **kwargs):  # pragma: nocover
    pass


def typed(arg: str):
    return type(arg)


def test_bind():
    sig = inspect.signature(foo)
    args, kwargs = (1, 2), {"kwd": "kwd", "kwarg": "kwarg"}
    builtin: inspect.BoundArguments = sig.bind(*args, **kwargs)
    baked = typic.bind(foo, *args, **kwargs)
    assert builtin.kwargs == baked.kwargs
    assert builtin.args == baked.args
    assert dict(builtin.arguments) == baked.arguments


def test_typed_no_coerce():
    bound = typic.bind(typed, 1, coerce=False)
    assert bound.arguments["arg"] == 1


@pytest.mark.parametrize(
    argnames=("func", "params"),
    argvalues=[
        (one, ((1, 1), {})),
        (one, ((), {})),
        (one, ((1,), {"arg": 1})),
        (kwd, ((1,), {})),
        (kwd, ((), {"foo": 1})),
        (kwarg, ((1, 1), {})),
    ],
)
def test_bind_errors(func, params):
    args, kwargs = params
    with pytest.raises(TypeError):
        typic.bind(func, *args, **kwargs)
