from __future__ import annotations

import builtins
import inspect
import os
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Type, TypeVar, overload

from typical import types
from typical.checks import STDLIB_TYPES
from typical.core import constants, interfaces
from typical.inspection import get_name

if TYPE_CHECKING:  # pragma: nocover
    from typical.core.resolver import Resolver


_ET = TypeVar("_ET", bound=object)


__all__ = (
    "Environ",
    "EnvironmentValueError",
    "EnvironmentTypeError",
)


class Environ:
    """A proxy for the os.environ which allows for getting/setting typed values."""

    def __init__(self, resolver: Resolver):
        self.resolver = resolver
        for t in STDLIB_TYPES:
            self.register(t)
        for name, t in inspect.getmembers(
            types, lambda o: inspect.isclass(o) and not issubclass(o, Exception)
        ):
            self.register(t, name=name)

    def __getattr__(self, item: _ET):
        if inspect.isclass(item):
            t: Type[_ET] | None = getattr(builtins, item, None)  # type: ignore[call-overload]
            if t is None:
                t = globals().get(item)  # type: ignore[call-overload]
            return self.register(t, name=get_name(t))
        raise AttributeError(
            f"{self.__class__.__name__!r} object has no attribute {item!r}"
        )

    def __contains__(self, item: str):
        return os.environ.__contains__(item)

    def __getitem__(self, item: str):
        return os.environ.__getitem__(item)

    def __setitem__(self, key: str, value):
        return self.setenv(key, value)

    def register(self, t: Type[_ET], *aliases: str, name: str = None) -> EnvGetter[_ET]:
        """Register a handler for the target type `t`."""
        anno = self.resolver.annotation(t)
        if isinstance(
            anno, (interfaces.ForwardDelayedAnnotation, interfaces.DelayedAnnotation)
        ):
            anno = anno.resolved.annotation  # type: ignore

        name = name or get_name(anno.resolved)
        if name in self.__dict__:
            return self.__dict__[name]

        if not inspect.isclass(anno.resolved):
            raise EnvironmentTypeError(
                f"Can't coerce to target {name!r} with t: {t!r}."
            ) from None

        def get(var: str, *, ci: bool = True, default: _ET = None):
            return self.getenv(var, default, *aliases, t=t, ci=ci)

        setattr(self, name, get)
        return get

    @overload
    def getenv(
        self,
        var: str,
        default: _ET = ...,
        *aliases: str,
        t: Type[_ET],
        ci: bool = ...,
    ) -> _ET:
        ...

    @overload
    def getenv(
        self,
        var: str,
        *aliases: str,
        ci: bool = ...,
    ) -> str | None:
        ...

    def getenv(
        self,
        var: str,
        default: _ET | type[constants.empty] = constants.empty,
        *aliases: str,
        t: Type[_ET] | type[constants.empty] = constants.empty,
        ci: bool = True,
    ) -> Any | None:
        """Get the value of an Environment Variable.

        Args:
            var: The environment variable to fetch.
            default: Provide a default value if `var` is not found.
            *aliases: Any potential aliases to search for if `var` is not found.

        Keyword Args:
            t: If provided, the type to validate the value against.
            ci: Whether the variable should be considered case-insensitive.
        """
        names: set[str] = {*aliases}
        environ: Mapping[str, str] = os.environ
        # If we should do a case-insensitive search, casefold everything first.
        if ci:
            var = var.lower()
            names = {v.lower() for v in aliases}
            environ = {k.lower(): value for k, value in os.environ.items()}
        value = environ.get(var, default)
        # If we got the default, and we have alternate names to search, do so.
        if value == default and names:
            value = next((environ[k] for k in environ.keys() & names), default)
        # If we have the default, return that.
        if value is not constants.empty:
            return value
        # Short-circuit for no type given.
        if issubclass(t, constants.empty):
            retval = None if value is constants.empty else value
            return retval

        proto: interfaces.SerdeProtocol[_ET] = self.resolver.resolve(t)
        # If we still have no value, and the given type is not optional, raise an error.
        if value is ... and not proto.annotation.optional:
            raise EnvironmentValueError(
                f"{var!r} should be of {t!r}, got nothing."
            ) from None
        try:
            # Otherwise, try to convert the found value to the given type.
            return proto.transmute(value)
        except (TypeError, ValueError, KeyError) as err:
            raise EnvironmentValueError(
                f"Couldn't parse <{var}:{value}> to {t!r}: {err}."
            ) from err

    def setenv(self, var: str, value: Any):
        """Set the `value` as `var` in the OS environ."""

        if not isinstance(value, (str, bytes)):
            value = self.resolver.tojson(value)
            if isinstance(value, bytes):
                value = value.decode()
        if isinstance(value, bytes):
            os.environb[var.encode()] = value
            return
        os.environ[var] = value


class EnvGetter(Protocol[_ET]):
    @overload
    def __call__(self, var: str, *, ci: bool = True, default: _ET) -> _ET:
        ...

    @overload
    def __call__(self, var: str, *, ci: bool = True) -> _ET | None:
        ...

    def __call__(self, var, *, ci=True, default=None):
        ...


class EnvironmentValueError(ValueError):
    ...


class EnvironmentTypeError(TypeError):
    ...
