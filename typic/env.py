from __future__ import annotations

import builtins
import inspect
import os
from typing import TypeVar, Type, Any, TYPE_CHECKING, Mapping

from typic import types
from typic.checks import STDLIB_TYPES
from typic.serde import common
from typic.util import get_name


if TYPE_CHECKING:  # pragma: nocover
    from typic.serde.resolver import Resolver


_ET = TypeVar("_ET")


class EnvironmentValueError(ValueError):
    ...


class EnvironmentTypeError(TypeError):
    ...


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

    def __getattr__(self, item):
        if inspect.isclass(item):
            t: Type[_ET] = getattr(builtins, item, None) or globals().get(item)
            return self.register(t, name=item)
        raise AttributeError(
            f"{self.__class__.__name__!r} object has no attribute {item!r}"
        )

    def __contains__(self, item):
        return os.environ.__contains__(item)

    def __getitem__(self, item):
        return os.environ.__getitem__(item)

    def __setitem__(self, key, value):
        return self.setenv(key, value)

    def register(self, t: Type[_ET], *aliases: str, name: str = None):
        """Register a handler for the target type `t`."""
        anno = self.resolver.annotation(t)
        if isinstance(
            anno, (common.ForwardDelayedAnnotation, common.DelayedAnnotation)
        ):
            anno = anno.resolved.annotation  # type: ignore

        name = name or get_name(anno.resolved)
        if name in self.__dict__:
            return self.__dict__[name]

        if not inspect.isclass(anno.resolved):
            raise EnvironmentTypeError(
                f"Can't coerce to target {name!r} with t: {t!r}."
            ) from None

        def get(var: str, *, ci: bool = True, default: _ET = ...):  # type: ignore
            return self.getenv(var, default, *aliases, t=t, ci=ci)

        setattr(self, name, get)
        return get

    def getenv(
        self,
        var: str,
        default: _ET = ...,  # type: ignore
        *aliases: str,
        t: Type[_ET] = Any,  # type: ignore
        ci: bool = True,
    ) -> _ET:
        """Get the value of an Environment Variable.

        Keyword Args:
            t: If provided, the type to validate the value against.
            ci: Whether the variable should be considered case-insensitive.
        """
        proto = self.resolver.resolve(t)
        names = {*aliases}
        environ: Mapping[str, str] = os.environ
        if ci:
            var = var.lower()
            names = {v.lower() for v in aliases}
            environ = {k.lower(): value for k, value in os.environ.items()}
        value = environ.get(var, default)
        if value == default and names:
            value = next((environ[k] for k in environ.keys() & names), default)
        if value is ... and t is Any:
            return None  # type: ignore
        if value is ... and not proto.annotation.optional:
            raise EnvironmentValueError(
                f"{var!r} should be of {t!r}, got nothing."
            ) from None
        if value == default:
            return value  # type: ignore
        try:
            return proto.transmute(value)  # type: ignore
        except (TypeError, ValueError, KeyError) as err:
            raise EnvironmentValueError(
                f"Couldn't parse <{var}:{value}> to {t!r}: {err}."
            ) from None

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
