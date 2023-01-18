from __future__ import annotations

import dataclasses
import inspect
import warnings
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar

from typical import classes, inspection
from typical.compat import Generic

_T = TypeVar("_T")

if TYPE_CHECKING:  # pragma: nocover
    from typing import Callable, Mapping, Tuple, Type, Union

    from typical.core.interfaces import (  # noqa: F401
        DeserializerT,
        SerdeProtocol,
        SerdeProtocolsT,
    )
    from typical.core.resolver import Resolver

    BindingT = Mapping[Union[str, int], DeserializerT]
    EnforcerT = Callable[..., Tuple[tuple, dict]]
    BindingCacheKeyT = Tuple[Union[Type[_T], Callable[..., _T]], bool]
    BindingCacheValueT = Tuple[
        Mapping[str, inspect.Parameter], SerdeProtocolsT, EnforcerT
    ]


__all__ = ("Binder", "BoundArguments")


class Binder:
    _ENFORCER_CACHE: dict[BindingCacheKeyT, BindingCacheValueT] = {}

    def __init__(self, resolver: Resolver):
        self.resolver = resolver

    @staticmethod
    def get_binding(
        parameters: Mapping[str, inspect.Parameter],
        protocols: SerdeProtocolsT,
    ) -> tuple[BindingT, DeserializerT | None, DeserializerT | None]:
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

    def get_enforcer(  # noqa: C901
        self,
        parameters: Mapping[str, inspect.Parameter],
        protocols: SerdeProtocolsT,
    ) -> EnforcerT:
        binding, vararg, varkwarg = self.get_binding(parameters, protocols)
        argixes = [k for k in binding if isinstance(k, int)]
        maxarg = max(argixes) + 1 if argixes else None
        if vararg and varkwarg:
            if maxarg:

                def enforce_binding_vararg_warkwarg_maxarg(
                    *args, __binding=binding, **kwargs
                ):
                    vargs = [
                        __binding[i](v) if i in __binding else v
                        for i, v in enumerate(args[:maxarg])
                    ]
                    vargs.extend((vararg(v) for v in args[maxarg:]))
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                    return vargs, kwargs

                return enforce_binding_vararg_warkwarg_maxarg

            def enforce_binding_vararg_varkwarg(*args, __binding=binding, **kwargs):
                vargs = [vararg(v) for v in args]
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                return vargs, kwargs

            return enforce_binding_vararg_varkwarg

        if vararg:
            if maxarg:

                def enforce_binding_vararg_maxarg(*args, __binding=binding, **kwargs):
                    vargs = [
                        __binding[i](v) if i in __binding else v
                        for i, v in enumerate(args[:maxarg])
                    ]
                    vargs.extend((vararg(v) for v in args[maxarg:]))
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else v
                    return vargs, kwargs

                return enforce_binding_vararg_maxarg

            def enforce_binding_vararg(*args, __binding=binding, **kwargs):
                vargs = [vararg(v) for v in args]
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v)
                return vargs, kwargs

            return enforce_binding_vararg

        if varkwarg:
            if argixes:

                def enforce_binding_varkwarg_posonly(
                    *args, __binding=binding, **kwargs
                ):
                    vargs = [__binding[i](v) for i, v in enumerate(args)]
                    for k, v in kwargs.items():
                        kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                    return vargs, kwargs

                return enforce_binding_varkwarg_posonly

            def enforce_binding_varkwarg(*args, __binding=binding, **kwargs):
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else varkwarg(v)
                return args, kwargs

            return enforce_binding_varkwarg

        if argixes:

            def enforce_binding_posonly(*args, __binding=binding, **kwargs):
                vargs = [__binding[i](v) for i, v in enumerate(args)]
                for k, v in kwargs.items():
                    kwargs[k] = __binding[k](v) if k in __binding else v
                return vargs, kwargs

            return enforce_binding_posonly

        def enforce_binding_kwdonly(*args, __binding=binding, **kwargs):
            for k, v in kwargs.items():
                kwargs[k] = __binding[k](v) if k in __binding else v
            return args, kwargs

        return enforce_binding_kwdonly

    def bind(
        self,
        obj: type[_T] | Callable[..., _T],
        *args: Any,
        partial: bool = None,
        coerce: bool = None,
        strict: bool = False,
        **kwargs: Mapping[str, Any],
    ) -> BoundArguments[_T]:
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
        >>> import typical
        >>>
        >>> def add(a: int, b: int, *, c: int = None) -> int:
        ...     return a + b + (c or 0)
        ...
        >>> bound = typical.bind(add, "1", "2", c=3.0)
        >>> bound.args
        ('1', '2')
        >>> bound.kwargs
        {'c': 3.0}
        >>> bound.eval()
        6
        >>> typical.bind(add, 1, 3.0, strict=True).eval()
        Traceback (most recent call last):
            ...
        typic.core.constraints.core.error.ConstraintValueError: Given value <3.0> fails constraints: (type=int)
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
        enforcer: EnforcerT
        if (obj, strict) in self.__class__._ENFORCER_CACHE:
            params, protocols, enforcer = self.__class__._ENFORCER_CACHE[(obj, strict)]
        else:
            params = inspection.cached_signature(obj).parameters
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


@classes.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True)
class BoundArguments(Generic[_T]):
    obj: type[_T] | Callable[..., _T]
    """The object we "bound" the input to."""
    annotations: SerdeProtocolsT
    """A mapping of the resolved annotations."""
    parameters: Mapping[str, inspect.Parameter]
    """A mapping of the parameters."""
    args: tuple[Any, ...]
    """A tuple of positional inputs."""
    kwargs: dict[str, Any]
    """A mapping of keyword inputs."""
    enforcer: EnforcerT

    def eval(self) -> _T:
        """Evaluate the callable against the input provided.

        Examples
        --------
        >>> import typical
        >>>
        >>> def foo(bar: int) -> int:
        ...     return bar ** bar
        ...
        >>> bound = typical.bind(foo, "2")
        >>> bound.eval()
        4
        """
        args, kwargs = self.enforcer(*self.args, **self.kwargs)  # type: ignore
        return self.obj(*args, **kwargs)  # type: ignore


class _binding(dict):
    def __missing__(self, key):
        return _empty_deser


def _empty_deser(v):
    return v
