from __future__ import annotations

import dataclasses
import inspect
import warnings
from types import MappingProxyType
from typing import (
    Dict,
    Any,
    Tuple,
    TYPE_CHECKING,
    Optional,
    Union,
    Type,
    Callable,
    Mapping,
    MutableMapping,
)

from typic import util

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver  # noqa: F401
    from .common import SerdeProtocol, SerdeProtocolsT, DeserializerT  # noqa: F401

    BindingT = Mapping[Union[str, int], DeserializerT]


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True)
class BoundArguments:
    obj: Union[Type, Callable]
    """The object we "bound" the input to."""
    annotations: SerdeProtocolsT
    """A mapping of the resolved annotations."""
    parameters: Mapping[str, inspect.Parameter]
    """A mapping of the parameters."""
    args: Tuple[Any, ...]
    """A tuple of positional inputs."""
    kwargs: Dict[str, Any]
    """A mapping of keyword inputs."""
    enforcer: Callable

    def eval(self) -> Any:
        """Evaluate the callable against the input provided.

        Examples
        --------
        >>> import typic
        >>>
        >>> def foo(bar: int) -> int:
        ...     return bar ** bar
        ...
        >>> bound = typic.bind(foo, "2")
        >>> bound.eval()
        4
        """
        args, kwargs = self.enforcer(*self.args, **self.kwargs)
        return self.obj(*args, **kwargs)


class Binder:
    _ENFORCER_CACHE: MutableMapping[Tuple[Union[Type, Callable], bool], Tuple] = {}

    def __init__(self, resolver: Resolver):
        self.resolver = resolver

    @staticmethod
    def get_binding(
        parameters, protocols
    ) -> Tuple[BindingT, Optional[DeserializerT], Optional[DeserializerT]]:
        binding = _binding()
        vararg = None
        varkwarg = None
        for i, (name, param) in enumerate(parameters.items()):
            des = protocols[name].transmute
            if param.kind == param.KEYWORD_ONLY:
                binding[name] = des
            elif param.kind == param.POSITIONAL_ONLY:  # pragma: nocover
                binding[i] = des
            elif param.kind == param.VAR_POSITIONAL:
                vararg = des
            elif param.kind == param.VAR_KEYWORD:
                varkwarg = des
            else:
                binding[i] = binding[name] = des
        return (
            MappingProxyType(binding),
            vararg,
            varkwarg,
        )

    def get_enforcer(self, parameters, protocols):  # noqa: C901
        binding, vararg, varkwarg = self.get_binding(parameters, protocols)
        argixes = [k for k in binding if isinstance(k, int)]
        maxarg = max(argixes) + 1 if argixes else None
        if vararg and varkwarg:
            if maxarg:

                def enforce_binding(*args, __binding=binding, **kwargs):
                    vargs = [...] * len(args)
                    for i, v in enumerate(args[:maxarg]):
                        vargs[i] = __binding[i](v) if i in binding else v
                    for i, v in enumerate(args[maxarg:], start=maxarg):
                        vargs[i] = vararg(v)
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                    return vargs, kwargs

                return enforce_binding

            def enforce_binding(*args, __binding=binding, **kwargs):
                vargs = [vararg(v) for v in args]
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                return vargs, kwargs

            return enforce_binding

        if vararg:
            if maxarg:

                def enforce_binding(*args, __binding=binding, **kwargs):
                    vargs = [...] * len(args)
                    for i, v in enumerate(args[:maxarg]):
                        vargs[i] = __binding[i](v) if i in __binding else v
                    for i, v in enumerate(args[maxarg:], start=maxarg):
                        vargs[i] = vararg(v)
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else v
                    return vargs, kwargs

                return enforce_binding

            def enforce_binding(*args, __binding=binding, **kwargs):
                vargs = [vararg(v) for v in args]
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v)
                return vargs, kwargs

            return enforce_binding

        if varkwarg:
            if argixes:

                def enforce_binding(*args, __binding=binding, **kwargs):
                    vargs = [...] * len(args)
                    for i, v in enumerate(args):
                        vargs[i] = __binding[i](v) if i in __binding else v
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                    return vargs, kwargs

                return enforce_binding

            def enforce_binding(*args, __binding=binding, **kwargs):
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                return args, kwargs

            return enforce_binding

        if argixes:

            def enforce_binding(*args, __binding=binding, **kwargs):
                vargs = [...] * len(args)
                for i, v in enumerate(args):
                    vargs[i] = __binding[i](v)
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else v
                return vargs, kwargs

            return enforce_binding

        def enforce_binding(*args, __binding=binding, **kwargs):
            for k, v in kwargs.items():
                kwargs[k] = __binding[k](v) if k in __binding else v
            return args, kwargs

        return enforce_binding

    def bind(
        self,
        obj: Union[Type, Callable],
        *args: Any,
        partial: bool = None,
        coerce: bool = None,
        strict: bool = False,
        **kwargs: Mapping[str, Any],
    ) -> BoundArguments:
        """Bind a received input to a callable or object's signature.

        If we can locate an annotation for any args or kwargs, we'll automatically
        coerce as well.

        This implementation is similar to :py:meth:`inspect.Signature.bind`,
        but is ~10-20% faster.
        We also use a cached the signature to avoid the expense of that call if possible.

        Parameters
        ----------
        obj
            The object you wish to bind your input to.
        *args
            The given positional args.
        partial
            Whether to bind a partial input.
        coerce
            Whether to coerce the input to the annotation provided.
        strict
            Whether to validate the input against the annotation provided.
        **kwargs
            The given keyword args.

        Returns
        -------
        :py:class:`BoundArguments`
            The bound and coerced arguments.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature

        Examples
        --------
        >>> import typic
        >>>
        >>> def add(a: int, b: int, *, c: int = None) -> int:
        ...     return a + b + (c or 0)
        ...
        >>> bound = typic.bind(add, "1", "2", c=3.0)
        >>> bound.args
        ('1', '2')
        >>> bound.kwargs
        {'c': 3.0}
        >>> bound.eval()
        6
        >>> typic.bind(add, 1, 3.0, strict=True).eval()
        Traceback (most recent call last):
            ...
        typic.constraints.error.ConstraintValueError: Given value <3.0> fails constraints: (type=int, nullable=False)
        """
        if isinstance(coerce, bool):  # pragma: nocover
            warnings.warn(
                "The keyword argument `coerce` is deprecated "
                "and will be removed in a future version.",
                category=DeprecationWarning,
            )
        if isinstance(partial, bool):  # pragma: nocover
            warnings.warn(
                "The keyword argument `partial` is deprecated "
                "and will be removed in a future version.",
                category=DeprecationWarning,
            )
        if (obj, strict) in self.__class__._ENFORCER_CACHE:
            params, protocols, enforcer = self.__class__._ENFORCER_CACHE[(obj, strict)]
        else:
            params = util.cached_signature(obj).parameters
            protocols = self.resolver.protocols(obj=obj, strict=strict)
            enforcer = self.get_enforcer(parameters=params, protocols=protocols)
            self.__class__._ENFORCER_CACHE[(obj, strict)] = params, protocols, enforcer

        return BoundArguments(
            obj=obj,
            annotations=protocols,
            parameters=params,
            args=args,
            kwargs=kwargs,
            enforcer=enforcer,
        )


class _binding(dict):
    def __missing__(self, key):
        return _empty_deser


def _empty_deser(v):
    return v
