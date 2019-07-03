#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import inspect
from collections import deque
from typing import Any, Iterable, Dict, Deque, Tuple

__all__ = ("bind",)


_TOO_MANY_POS = "too many positional arguments"
_VAR_POSITIONAL = inspect._VAR_POSITIONAL
_VAR_KEYWORD = inspect._VAR_KEYWORD
_KEYWORD_ONLY = inspect._KEYWORD_ONLY
_POSITIONAL_ONLY = inspect._POSITIONAL_ONLY
_KWD_KINDS = {_VAR_KEYWORD, _KEYWORD_ONLY}
_POS_KINDS = {_VAR_POSITIONAL, _POSITIONAL_ONLY}
_empty = inspect._empty


@dataclasses.dataclass
class BoundArguments:
    signature: inspect.Signature
    arguments: Dict[str, Any]
    _argnames: Tuple[str]
    _kwdargnames: Tuple[str]

    @property
    def args(self) -> Tuple[Any]:
        args = list()
        argsappend = args.append
        argsextend = args.extend
        parameters = self.signature.parameters
        for name in self._argnames:
            kind = parameters[name].kind
            arg = self.arguments[name]
            if kind == _VAR_POSITIONAL:
                argsextend(arg)
            else:
                argsappend(arg)
        return tuple(args)

    @property
    def kwargs(self) -> Dict[str, Any]:
        arguments = self.arguments
        parameters = self.signature.parameters
        kwargs = {}
        kwargsupdate = kwargs.update
        kwargsset = kwargs.__setitem__
        for name in self._kwdargnames:
            kind = parameters[name].kind
            arg = arguments[name]
            if kind == _VAR_KEYWORD:
                kwargsupdate(arg)
            else:
                kwargsset(name, arg)
        return kwargs


def _bind_posargs(
    arguments: Dict[str, Any],
    parameters: Deque[inspect.Parameter],
    args: Deque[Any],
    kwargs: Dict[str, Any],
) -> Tuple[Any]:
    posargs = list()
    posargsadd = posargs.append
    argspop = args.popleft
    paramspop = parameters.popleft
    while args and parameters:
        val = argspop()
        param = paramspop()
        kind = param.kind
        name = param.name
        # We've got varargs, so push all supplied args to that param.
        if kind == _VAR_POSITIONAL:
            value = (val,) + tuple(args)
            arguments[name] = value
            posargsadd(name)
            break

        # We're not supposed to have kwdargs....
        if kind in _KWD_KINDS:
            raise TypeError(_TOO_MANY_POS) from None

        # Passed in by ref and assignment... no good.
        if name in kwargs:
            raise TypeError(f"multiple values for argument '{name}'") from None

        # We're g2g
        arguments[name] = val
        posargsadd(name)

    if args:
        raise TypeError(_TOO_MANY_POS) from None

    return tuple(posargs)


def _bind_kwdargs(
    arguments: Dict[str, Any],
    parameters: Deque[inspect.Parameter],
    kwargs: Dict[str, Any],
    partial: bool = False,
) -> Tuple[str]:
    # Bind any key-word arguments
    kwdargs = list()
    kwdargsadd = kwdargs.append
    kwargs_param = None
    kwargspop = kwargs.pop
    for param in parameters:
        kind = param.kind
        # Move on, but don't forget
        if kind == _VAR_KEYWORD:
            kwargs_param = param
            continue
        # We don't care about these
        if kind == _VAR_POSITIONAL:
            continue

        name = param.name
        try:
            val = kwargspop(name)
            if kind == _POSITIONAL_ONLY:
                raise TypeError(
                    f"{name!r} parameter is positional only,"
                    "but was passed as a keyword."
                )
            arguments[name] = val
            kwdargsadd(name)
        except KeyError:
            if not partial and param.default is _empty:
                raise TypeError(f"missing required argument: {name!r}")
    if kwargs:
        if kwargs_param is not None:
            # Process our '**kwargs'-like parameter
            name = kwargs_param.name
            arguments[name] = kwargs
            kwdargsadd(name)
        else:
            raise TypeError(
                f"'got an unexpected keyword argument {next(iter(kwargs))!r}'"
            )

    return tuple(kwdargs)


def bind(
    sig: inspect.Signature,
    args: Iterable[Any],
    kwargs: Dict[str, Any],
    *,
    partial: bool = False,
) -> BoundArguments:
    """Taken approximately from :py:meth:`inspect.Signature.bind`, with a few changes.

    About 10% faster, on average.
    """
    arguments = dict()
    parameters = deque(sig.parameters.values())
    args = deque(args)
    # Bind any positional arguments.
    posargs = _bind_posargs(arguments, parameters, args, kwargs)
    # Bind any keyword arguments.
    kwdargs = _bind_kwdargs(arguments, parameters, kwargs, partial)
    return BoundArguments(sig, arguments, posargs, kwdargs)
