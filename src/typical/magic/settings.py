from __future__ import annotations

import collections
import dataclasses
import functools
from typing import Callable, Mapping, Type, overload

from typical.api import resolver
from typical.core.annotations import ObjectT
from typical.env import Environ
from typical.inspection import cached_type_hints
from typical.magic.typed import WrappedObjectT, wrap_cls

__all__ = (
    "environ",
    "settings",
)

environ = Environ(resolver)


@overload
def settings(_klass: Type[ObjectT]) -> Type[WrappedObjectT[ObjectT]]:
    ...


@overload
def settings(
    *,
    prefix: str = "",
    case_sensitive: bool = False,
    frozen: bool = True,
    aliases: Mapping = None,
) -> Callable[[Type[ObjectT]], Type[WrappedObjectT[ObjectT]]]:
    ...


def settings(
    _klass=None,
    *,
    prefix: str = "",
    case_sensitive: bool = False,
    frozen: bool = True,
    aliases: Mapping = None,
):
    """Create a typed class which fetches its defaults from env vars.

    The resolution order of values is `default(s) -> env value(s) -> passed value(s)`.

    Settings instances are indistinguishable from other `typical` dataclasses at
    run-time and are frozen by default. If you really want your settings to be mutable,
    you may pass in `frozen=False` manually.

    Parameters
    ----------
    prefix
        The prefix to strip from you env variables, i.e., `APP_`
    case_sensitive
        Whether your variables are case-sensitive. Defaults to `False`.
    frozen
        Whether to generate a frozen dataclass. Defaults to `True`
    aliases
        An optional mapping of potential aliases for your dataclass's fields.
        `{'other_foo': 'foo'}` will locate the env var `OTHER_FOO` and place it
        on the `Bar.foo` attribute.

    Examples
    --------
    >>> import typical
    >>> from typical import magic
    >>>
    >>> magic.environ['FOO'] = "1"
    >>>
    >>> @magic.settings
    ... class Bar:
    ...     foo: int
    ...
    >>> Bar()
    Bar(foo=1)
    >>> Bar("3")
    Bar(foo=3)
    >>> bar = Bar()
    >>> bar.foo = 2
    Traceback (most recent call last):
    ...
    dataclasses.FrozenInstanceError: cannot assign to field 'foo'
    """
    aliases = aliases or {}

    def settings_wrapper(_cls):
        _resolve_from_env(_cls, prefix, case_sensitive, aliases)
        cls = wrap_cls(
            dataclasses.dataclass(_cls, frozen=frozen), jsonschema=False, always=False
        )
        return cls

    return settings_wrapper(_klass) if _klass is not None else settings_wrapper


def _resolve_from_env(
    cls: Type[ObjectT],
    prefix: str,
    case_sensitive: bool,
    aliases: Mapping[str, str],
) -> Type[ObjectT]:
    fields = cached_type_hints(cls)
    vars = {
        (f"{prefix}{x}".lower() if not case_sensitive else f"{prefix}{x}"): (x, y)
        for x, y in fields.items()
    }
    attr_to_aliases = collections.defaultdict(set)
    for alias, attr in aliases.items():
        attr_to_aliases[attr].add(alias)

    sentinel = object()
    for name in vars:
        attr, typ = vars[name]
        names = attr_to_aliases[name]
        field = getattr(cls, attr, sentinel)
        if field is sentinel:
            field = dataclasses.field()
        elif not isinstance(field, dataclasses.Field):
            field = dataclasses.field(default=field)
        if field.default_factory != dataclasses.MISSING:
            continue

        kwargs = dict(var=name, ci=not case_sensitive)
        if field.default != dataclasses.MISSING:
            kwargs["default"] = field.default
            field.default = dataclasses.MISSING

        factory = environ.register(typ, *names, name=name)
        field.default_factory = functools.partial(factory, **kwargs)
        setattr(cls, attr, field)

    return cls
