from __future__ import annotations

import builtins
import inspect
import os
from typing import TypeVar, Type, Any, TYPE_CHECKING

from typic import types
from typic.checks import STDLIB_TYPES
from typic.util import get_name


if TYPE_CHECKING:
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

    def register(self, t: Type[_ET], *, name: str = None):
        """Register a handler for the target type `t`."""
        name = name or get_name(t)
        if name in self.__dict__:
            return self.__dict__[name]

        if not inspect.isclass(t):
            raise EnvironmentTypeError(
                f"Can't coerce to target {name!r} with t: {t!r}."
            ) from None

        def get(var: str, *, ci: bool = True):
            return self.getenv(var, t=t, ci=ci)

        setattr(self, name, get)
        return get

    def getenv(
        self,
        var: str,
        default: _ET = None,
        *,
        t: Type[_ET] = Any,  # type: ignore
        ci: bool = True,
    ) -> _ET:
        """Get the value of an Environment Variable.

        Keyword Args:
            t: If provided, the type to validate the value against.
            ci: Whether the variable should be considered case-insensitive.
        """
        proto = self.resolver.resolve(t)
        value = os.environ.get(var)
        if value is None and ci:
            value = next(
                (v for k, v in os.environ.items() if k.lower() == var.lower()), None
            )
        if value is None and t is Any:
            return default  # type: ignore
        if value is None and not proto.annotation.optional:
            raise EnvironmentValueError(
                f"{var!r} should be of {t!r}, got nothing."
            ) from None
        try:
            return proto.transmute(value)  # type: ignore
        except (TypeError, ValueError) as err:
            raise EnvironmentValueError(
                f"Couldn't parse <{var}:{value}> to {t!r}: {err}."
            ) from None

    def setenv(self, var: str, value: Any):
        """Set the `value` as `var` in the OS environ."""
        if isinstance(value, bytes):
            os.environb[var.encode()] = value
            return
        elif not isinstance(value, str):
            value = self.resolver.tojson(value)
        os.environ[var] = value
