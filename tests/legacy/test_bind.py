from __future__ import annotations

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


def test_typed_arg():
    def func(arg: str):
        return arg

    assert typic.bind(func, 1).eval() == typic.bind(func, arg=1).eval() == "1"


def test_typed_arg_varg():
    def func(arg: str, *args: int):
        return arg, args

    assert typic.bind(func, 1).eval() == typic.bind(func, arg=1).eval() == ("1", ())
    assert typic.bind(func, 1, "1").eval() == ("1", (1,))


def test_typed_arg_varg_kwarg():
    def func(arg: str, *args: int, **kwargs: str):
        return arg, args, kwargs

    assert typic.bind(func, 1).eval() == typic.bind(func, arg=1).eval() == ("1", (), {})
    assert typic.bind(func, 1, "1").eval() == ("1", (1,), {})
    assert typic.bind(func, 1, "1", k=1).eval() == ("1", (1,), {"k": "1"})


def test_typed_varg():
    def func(*args: str):
        return args

    assert typic.bind(func).eval() == ()
    assert typic.bind(func, 1).eval() == ("1",)


def test_typed_kwarg():
    def func(**kwargs: str):
        return kwargs

    assert typic.bind(func).eval() == {}
    assert typic.bind(func, k=1).eval() == {"k": "1"}


def test_typed_arg_kwarg():
    def func(arg: str, **kwargs: str):
        return arg, kwargs

    assert typic.bind(func, 1).eval() == typic.bind(func, arg=1).eval() == ("1", {})
    assert (
        typic.bind(func, 1, k=1).eval()
        == typic.bind(func, k=1, arg=1).eval()
        == ("1", {"k": "1"})
    )


def test_typed_args_kwd():
    def func(*args: int, kwd: str):
        return args, kwd

    assert typic.bind(func, "1", kwd=1).eval() == ((1,), "1")


def test_bind():
    sig = inspect.signature(foo)
    args, kwargs = (1, 2), {"kwd": "kwd", "kwarg": "kwarg"}
    builtin: inspect.BoundArguments = sig.bind(*args, **kwargs)
    baked = typic.bind(foo, *args, **kwargs)
    assert builtin.kwargs == baked.kwargs
    assert builtin.args == baked.args


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
        typic.bind(func, *args, **kwargs).eval()
