#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import functools
import inspect
import dataclasses
import os
from typing import (
    Union,
    Callable,
    Type,
    Any,
    Tuple,
    Optional,
    Mapping,
    TypeVar,
    Generic,
    cast,
)

import typic.constraints as c
from typic.checks import issubclass, ishashable
from typic.coercer import (
    TypeCoercer as __TypeCoercer,
    _TO_RESOLVE,
    _ORIG_SETTER_NAME,
    _origsettergetter,
    BoundArguments,
    ResolvedAnnotation,
)
from typic.util import origin, primitive

__all__ = (
    "annotations",
    "bind",
    "coerce",
    "register",
    "resolve",
    "settings",
    "schema",
    "schemas",
    "typed",
    "wrap",
    "wrap_cls",
    "constrained",
    "BoundArguments",
    "ResolvedAnnotation",
)

Object = TypeVar("Object")

coerce: __TypeCoercer = __TypeCoercer()
bind = coerce.bind
register = coerce.register
annotations = coerce.annotations
schema = coerce.schema
schemas = coerce.schema_builder.all

_T = TypeVar("_T")


class TypicObject(Generic[_T]):

    schema = classmethod(schema)
    primitive = primitive


def wrap(func: Callable, *, delay: bool = False) -> Callable:
    """Wrap a callable to automatically enforce type-coercion.

    Parameters
    ----------
    func
        The callable for which you wish to ensure type-safety
    delay
        Delay annotation resolution until the first call

    See Also
    --------
    :py:func:`inspect.signature`
    :py:meth:`inspect.Signature.bind`
    """
    if not delay:
        coerce.annotations(func)
    else:
        _TO_RESOLVE.append(func)

    @functools.wraps(func)
    def func_wrapper(*args, **kwargs) -> Any:
        bound = coerce.bind(func, *args, **kwargs)
        return func(*bound.args, **bound.kwargs)

    return func_wrapper


def wrap_cls(
    klass: Type[Object], *, delay: bool = False
) -> Type[TypicObject[Type[Object]]]:
    """Wrap a class to automatically enforce type-coercion on init.

    Notes
    -----
    While ``Coercer.wrap`` will work with classes alone, it changes the signature of the
    object to a function, there-by breaking inheritance. This follows a similar pattern to
    :func:`dataclasses.dataclasses`, which executes the function when wrapped, preserving
    the signature of the target class.

    Parameters
    ----------
    klass
        The class you wish to patch with coercion.
    delay
        Delay annotation resolution until first initialization.
    """
    # Resolve the annotations. This will store them on the object as well
    if not delay:
        coerce.annotations(klass)
        coerce.schema(klass)
    else:
        _TO_RESOLVE.append(klass)

    def cls_wrapper(cls_: Type[Object]) -> Type[TypicObject[Type[Object]]]:
        cls_.schema = classmethod(coerce.schema)  # type: ignore
        cls_.primitive = primitive  # type: ignore
        # Frozen dataclasses don't use the native setattr
        # So we wrap the init. This should be fine,
        # just slower :(
        if (
            hasattr(cls_, "__dataclass_params__")
            and cls_.__dataclass_params__.frozen  # type: ignore
        ):
            cls_.__init__ = wrap(cls_.__init__, delay=delay)  # type: ignore
        else:
            setattr(cls_, _ORIG_SETTER_NAME, _get_setter(cls_))
            cls_.__setattr__ = __setattr_coerced__  # type: ignore
        return cls_  # type: ignore

    wrapped = cls_wrapper(klass)
    return wrapped


def __setattr_coerced__(self, name, value):
    ann = annotations(type(self))
    value = ann[name](value) if name in ann else value
    _origsettergetter(self)(name, value)


def _get_setter(cls: Type, bases: Tuple[Type, ...] = None):
    bases = bases or cls.__bases__
    setter = cls.__setattr__
    if setter is __setattr_coerced__:
        for base in bases:
            name = (
                _ORIG_SETTER_NAME if hasattr(base, _ORIG_SETTER_NAME) else "__setattr__"
            )
            setter = getattr(base, name, None)
            if setter is not __setattr_coerced__:
                break
    return setter


def typed(_cls_or_callable=None, *, delay: bool = False):
    """A convenience function which automatically selects the correct wrapper.

    Parameters
    ----------
    delay
        Optionally delay annotation resolution until first call.

    Returns
    -------
    The target object, appropriately wrapped.
    """

    def _typed(obj: Union[Callable, Type[Object]]):
        if inspect.isclass(obj):
            return wrap_cls(obj, delay=delay)  # type: ignore
        elif isinstance(obj, Callable):  # type: ignore
            return wrap(obj, delay=delay)  # type: ignore
        else:
            raise TypeError(
                f"{__name__} requires a callable or class. Provided: {type(obj)}: {obj}"
            )

    return _typed(_cls_or_callable) if _cls_or_callable is not None else _typed


def resolve():
    """Resolve any delayed annotations.

    If this is not called, annotations will be resolved on first call
    of the wrapped class or callable.

    Examples
    --------
    >>> import typic
    >>>
    >>> @typic.klass(delay=True)
    ... class Duck:
    ...     color: str
    ...
    >>> typic.resolve()
    """
    while _TO_RESOLVE:
        obj = _TO_RESOLVE.pop()
        annotations(obj)
        if inspect.isclass(obj):
            schema(obj)


_CONSTRAINT_TYPE_MAP = {x.type: x for x in c.Constraints.__args__}  # type: ignore


def _get_constraint_cls(cls: Type) -> Optional[Type[c.Constraints]]:
    if cls in _CONSTRAINT_TYPE_MAP:  # pragma: nocover
        return _CONSTRAINT_TYPE_MAP[cls]
    for typ, constr in _CONSTRAINT_TYPE_MAP.items():
        if issubclass(origin(cls), typ):
            _CONSTRAINT_TYPE_MAP[cls] = constr
            return constr

    return None


def constrained(
    _klass=None, *, values: Union[Type, Tuple[Type, ...]] = None, **constraints
):
    """A wrapper to indicate a 'constrained' type.

    Parameters
    ----------
    values
        For container-types, you can pass in other constraints for the values to be
        validated against. Can be a single constraint for all values or a tuple of
        constraints to choose from.

    **constraints
        The restrictions to apply to values being cast as the decorated type.

    Examples
    --------
    >>> import typic
    >>>
    >>> @typic.constrained(max_length=10)
    ... class ShortStr(str):
    ...     '''A short string.'''
    ...     ...
    ...
    >>> ShortStr('foo')
    'foo'
    >>> ShortStr('waytoomanycharacters')
    Traceback (most recent call last):
    ...
    typic.constraints.error.ConstraintValueError: Given value <'waytoomanycharacters'> fails constraints: (type=str, max_length=10)
    >>> @typic.constrained(values=ShortStr, max_items=2)
    ... class SmallMap(dict):
    ...     '''A small map that only allows short strings.'''
    ...
    >>> import json
    >>> print(json.dumps(typic.schema(SmallMap, primitive=True), indent=2))
    {
      "type": "object",
      "title": "SmallMap",
      "description": "A small map that only allows short strings.",
      "additionalProperties": {
        "type": "string",
        "maxLength": 10
      },
      "maxProperties": 2
    }


    See Also
    --------
    :py:mod:`typic.constraints.array`

    :py:mod:`typic.constraints.common`

    :py:mod:`typic.constraints.error`

    :py:mod:`typic.constraints.mapping`

    :py:mod:`typic.constraints.number`

    :py:mod:`typic.constraints.text`
    """

    def constr_wrapper(cls_: Type[Object]) -> Type[Object]:
        nonlocal constraints
        nonlocal values
        constr_cls = _get_constraint_cls(cls_)
        if not constr_cls:
            raise TypeError(f"can't constrain type {cls_.__name__!r}")

        if values and constr_cls.type in {list, dict, set, tuple, frozenset}:
            values = (
                tuple(x.__constraints__ for x in values)
                if isinstance(values, tuple)
                else values.__constraints__
            )
            key = "additional_items" if constr_cls.type == dict else "items"
            constraints[key] = values

        constraints_inst = constr_cls(**constraints)
        cdict = dict(cls_.__dict__)
        cdict.pop("__dict__", None)
        cdict.pop("__weakref__", None)
        bases = inspect.getmro(cls_)

        def new(_new):
            @functools.wraps(_new)
            def __constrained_new(*args, **kwargs):
                result = _new(*args, **kwargs)
                return constraints_inst.validate(result)

            return __constrained_new

        def init(_init):
            @functools.wraps(_init)
            def __constrained_init(self, *args, **kwargs):
                _init(self, *args, **kwargs)
                constraints_inst.validate(self)

            return __constrained_init

        cdict.update(
            __constraints__=constraints_inst,
            __origin__=constraints_inst.type,
            **(
                {"__new__": new(cls_.__new__)}
                if constraints_inst.type in {str, bytes, int, float}
                else {"__init__": init(cls_.__init__)}
            ),
        )
        cls: Type[Object] = cast(Type[Object], type(cls_.__name__, bases, cdict))

        return cls

    return constr_wrapper(_klass) if _klass else constr_wrapper


def _resolve_from_env(
    cls: Type[Object],
    prefix: str,
    case_sensitive: bool,
    aliases: Mapping[str, str],
    *,
    environ: Mapping[str, str] = None,
) -> Type[Object]:
    environ = environ or os.environ
    env = {(x.lower() if not case_sensitive else x): y for x, y in environ.items()}
    fields = {
        (f"{prefix}{x}".lower() if not case_sensitive else f"{prefix}{x}"): (x, y)
        for x, y in cls.__annotations__.items()
    }
    names = {*fields, *aliases}
    sentinel = object()
    for k in env.keys() & names:
        name = aliases.get(k, k)
        attr, typ = fields[name]
        val = coerce(env[k], typ)
        use_factory = not ishashable(val)
        field = getattr(cls, attr, sentinel)
        if not isinstance(field, dataclasses.Field):
            field = dataclasses.field()
        if use_factory:
            field.default_factory = lambda: val
            field.default = dataclasses.MISSING
        else:
            field.default = val
            field.default_factory = dataclasses.MISSING
        setattr(cls, attr, field)

    return cls


def settings(
    _klass: Type[Object] = None,
    *,
    prefix: str = "",
    case_sensitive: bool = False,
    frozen: bool = True,
    aliases: Mapping = None,
) -> Type[Object]:
    """Create a typed class which sets its defaults from env vars.

    The resolution order of values is ``default(s) -> env value(s) -> passed value(s)``.

    Settings instances are indistinguishable from other ``typical`` dataclasses at
    run-time and are frozen by default. If you really want your settings to be mutable,
    you may pass in ``frozen=False`` manually.

    Parameters
    ----------
    prefix
        The prefix to strip from you env variables, i.e., ``APP_``
    case_sensitive
        Whether your variables are case-sensitive. Defaults to ``False``.
    frozen
        Whether to generate a frozen dataclass. Defaults to ``True``
    aliases
        An optional mapping of potential aliases for your dataclass's fields.
        ``{'other_foo': 'foo'}`` will locate the env var ``OTHER_FOO`` and place it
        on the ``Bar.foo`` attribute.

    Notes
    -----
    Environment variables are resolved at compile-time, so updating your env after your
    typed classes are loaded into the namespace will not work.

    If you are using dotenv based configuration, you should read your dotenv file(s)
    into the env *before* initializing the module where your settings are located.

    A structure might look like:

    ::

        my-project/
        -- env/
        ..  -- .env.default
        ..  -- .env.local
        ..      ...
        ..  -- __init__.py  # load your dotenv files here
        ..  -- settings.py  # define your classes


    This will ensure your dotenv files are loaded into the environment before the Python
    interpreter parses & compiles your config classes, since the Python parser parses
    the init file before parsing anything else under the directory.

    Examples
    --------
    >>> import os
    >>> import typic
    >>>
    >>> os.environ['FOO'] = "1"
    >>>
    >>> @typic.settings
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
        cls = wrap_cls(dataclasses.dataclass(_cls, frozen=frozen))
        return cls

    return settings_wrapper(_klass) if _klass is not None else settings_wrapper
