#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import functools
import inspect
import dataclasses
import os
from collections import deque
from operator import attrgetter
from types import FunctionType, MethodType
from typing import (
    Union,
    Callable,
    Type,
    Tuple,
    Optional,
    Mapping,
    TypeVar,
    cast,
    Iterable,
    Any,
    Deque,
)

import typic.constraints as c
from typic.checks import issubclass, ishashable
from typic.serde.binder import BoundArguments
from typic.serde.common import (
    Annotation,
    SerdeFlags,
    SerializerT,
    SerdeProtocol,
    ProtocolsT,
    DeserializerT,
)
from typic.common import (
    ORIG_SETTER_NAME,
    SCHEMA_NAME,
    SERDE_FLAGS_ATTR,
    Case,
    ReadOnly,
    WriteOnly,
)
from typic.serde.resolver import resolver
from typic.strict import is_strict_mode, strict_mode, Strict, StrictStrT
from typic.ext.schema import SchemaFieldT, builder as schema_builder, ObjectSchemaField
from typic.util import origin
from typic.types import FrozenDict

__all__ = (
    "Annotation",
    "annotations",
    "bind",
    "BoundArguments",
    "Case",
    "coerce",
    "constrained",
    "is_strict_mode",
    "primitive",
    "protocol",
    "protocols",
    "ReadOnly",
    "register",
    "resolve",
    "resolver",
    "settings",
    "schema",
    "schemas",
    "SerdeFlags",
    "SerdeProtocol",
    "Strict",
    "strict_mode",
    "StrictStrT",
    "transmute",
    "typed",
    "wrap",
    "wrap_cls",
    "WriteOnly",
)

ObjectT = TypeVar("ObjectT")
SchemaGenT = Callable[[Type[ObjectT]], SchemaFieldT]
_TO_RESOLVE: Deque[Union[Type["WrappedObjectT"], Callable]] = deque()


transmute = resolver.transmute
bind = resolver.bind
register = resolver.des.register
primitive = resolver.primitive
schemas = schema_builder.all
protocols = resolver.protocols
protocol = resolver.resolve

# TBDeprecated
coerce = resolver.coerce_value
annotations = resolver.protocols


_T = TypeVar("_T")


class TypicObjectT:
    __serde__: SerdeProtocol
    __serde_flags__: SerdeFlags
    schema: SchemaGenT
    primitive: SerializerT
    transmute: DeserializerT


WrappedObjectT = Union[TypicObjectT, ObjectT]


def wrap(
    func: Callable[..., _T], *, delay: bool = False, strict: bool = False
) -> Callable[..., _T]:
    """Wrap a callable to automatically enforce type-coercion.

    Parameters
    ----------
    func
        The callable for which you wish to ensure type-safety
    delay
        Delay annotation resolution until the first call
    strict
        Turn on "validator mode": e.g. validate incoming data rather than coerce.

    See Also
    --------
    :py:func:`inspect.signature`
    :py:meth:`inspect.Signature.bind`
    """
    if not delay:
        protocols(func)
    else:
        _TO_RESOLVE.append(func)

    @functools.wraps(func)
    def func_wrapper(*args, **kwargs) -> _T:
        bound = bind(func, *args, strict=strict, **kwargs)
        return bound.eval()

    return func_wrapper


_sentinel = object()
_origsettergetter = attrgetter(ORIG_SETTER_NAME)


def wrap_cls(
    klass: Type[ObjectT],
    *,
    delay: bool = False,
    strict: bool = False,
    jsonschema: bool = True,
    serde: SerdeFlags = SerdeFlags(),
) -> Type[WrappedObjectT]:
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
    strict
        Turn on "validator mode": e.g. validate incoming data rather than coerce.
    jsonschema
        Generate a JSON Schema entry for this object.
    serde
        Optional settings for serialization/deserialization
    """

    def cls_wrapper(cls_: Type[ObjectT]) -> Type[WrappedObjectT]:
        nonlocal serde
        protos: Optional[ProtocolsT] = None
        # Frozen dataclasses don't use the native setattr
        # So we wrap the init. This should be fine,
        # just slower :(
        if (
            hasattr(cls_, "__dataclass_params__")
            and cls_.__dataclass_params__.frozen  # type: ignore
        ):
            cls_.__init__ = wrap(  # type: ignore
                cls_.__init__, delay=delay, strict=strict
            )
        else:

            def __setattr_coerced__(self, name, value):
                nonlocal protos
                protos = protos or protocols(type(self))
                value = protos[name](value) if name in protos else value
                _origsettergetter(self)(name, value)

            setattr(cls_, ORIG_SETTER_NAME, _get_setter(cls_))
            cls_.__setattr__ = __setattr_coerced__  # type: ignore

        cls = cast(Type[WrappedObjectT], cls_)
        if jsonschema:
            cls.schema = classmethod(schema)
        if hasattr(cls, SERDE_FLAGS_ATTR):
            serde = cls.__serde_flags__
        cls.__serde_flags__ = serde

        if not delay:
            protos = protocols(cls, strict=strict)
            resolved: SerdeProtocol = resolver.resolve(cls, is_strict=strict)
            cls.__serde__ = resolved
            cls.transmute = staticmethod(resolved.transmute)
            cls.primitive = resolved.primitive
            if jsonschema:
                schema(cls_)
        else:
            _TO_RESOLVE.append(cls)
        return cls_  # type: ignore

    wrapped: Type[WrappedObjectT] = cls_wrapper(klass)
    return wrapped


def _get_setter(cls: Type, bases: Tuple[Type, ...] = None):
    bases = bases or cls.__bases__
    setter = cls.__setattr__
    if setter.__name__ == "__setattr_coerced__":
        for base in bases:
            name = (
                ORIG_SETTER_NAME if hasattr(base, ORIG_SETTER_NAME) else "__setattr__"
            )
            setter = getattr(base, name, None)
            if setter.__name__ != "__setattr_coerced__":
                break
    return setter


def typed(_cls_or_callable=None, *, delay: bool = False, strict: bool = None):
    """A convenience function which automatically selects the correct wrapper.

    Parameters
    ----------
    delay
        Optionally delay annotation resolution until first call.
    strict
        Turn on "validator mode": e.g. validate incoming data rather than coerce.

    Returns
    -------
    The target object, appropriately wrapped.
    """

    def _typed(obj: Union[Callable, Type[ObjectT]]):
        if inspect.isclass(obj):
            return wrap_cls(obj, delay=delay, strict=strict)  # type: ignore
        elif isinstance(obj, Callable):  # type: ignore
            return wrap(obj, delay=delay, strict=strict)  # type: ignore
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
            resolved: SerdeProtocol = resolver.resolve(obj)
            obj.__serde__ = resolved  # type: ignore
            obj.transmute = staticmethod(resolved.transmute)
            obj.primitive = resolved.primitive


_CONSTRAINT_TYPE_MAP = {
    x.type: x
    for x in c.ConstraintsT.__args__  # type: ignore
    if hasattr(x, "type") and x.type != object
}


def _get_constraint_cls(cls: Type) -> Optional[Type[c.ConstraintsT]]:
    if cls in _CONSTRAINT_TYPE_MAP:  # pragma: nocover
        return _CONSTRAINT_TYPE_MAP[cls]
    for typ, constr in _CONSTRAINT_TYPE_MAP.items():
        if issubclass(origin(cls), typ):
            _CONSTRAINT_TYPE_MAP[cls] = constr
            return constr

    return None


def _get_maybe_multi_constraints(
    v,
) -> Union[c.ConstraintsT, Tuple[c.ConstraintsT, ...]]:
    cons: Union[c.ConstraintsT, Tuple[c.ConstraintsT, ...]]
    if isinstance(v, Iterable):
        cons_gen = (c.get_constraints(x) for x in v)
        cons = tuple((x for x in cons_gen if x is not None))
    else:
        cons = c.get_constraints(v)
    return cons


def _handle_constraint_values(constraints, values, args):
    vcons = _get_maybe_multi_constraints(values)
    if vcons:
        constraints["values"] = vcons
        if not isinstance(values, tuple) or len(values) == 1:
            args = (
                values  # type: ignore
                if isinstance(values, tuple)
                else (values,)
            )
    return args


def _handle_constraint_keys(constraints, args):
    if "keys" in constraints:
        ks = constraints["keys"]
        kcons = _get_maybe_multi_constraints(ks)
        if kcons:
            constraints["keys"] = kcons
        if not isinstance(ks, tuple) or len(ks) == 1:
            args = (ks if isinstance(ks, tuple) else (ks,)) + args
            if len(args) == 1:
                args = args + (Any,)
    if len(args) == 1:
        args = (Any,) + args
    for k in ("items", "patterns", "key_dependencies"):
        if k in constraints:
            f = {}
            for n, c_ in constraints[k].items():
                c__cons = _get_maybe_multi_constraints(c_)
                if c__cons:
                    f[n] = c__cons

            constraints[k] = FrozenDict(f)
    return args


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
    typic.constraints.error.ConstraintValueError: Given value <'waytoomanycharacters'> fails constraints: (type=str, nullable=False, coerce=False, max_length=10)
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

    def constr_wrapper(cls_: Type[ObjectT]) -> Type[ObjectT]:
        nonlocal constraints
        nonlocal values
        cdict = dict(cls_.__dict__)
        cdict.pop("__dict__", None)
        cdict.pop("__weakref__", None)
        constr_cls = _get_constraint_cls(cls_)
        if not constr_cls:
            raise TypeError(f"can't constrain type {cls_.__name__!r}")

        args: Tuple[Type, ...] = ()
        if values and constr_cls.type in {list, dict, set, tuple, frozenset}:
            args = _handle_constraint_values(constraints, values, args)
        if constr_cls.type == dict:
            args = _handle_constraint_keys(constraints, args)
        if args:
            cdict["__args__"] = args

        constraints_inst = constr_cls(**constraints)
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
            __parent__=constraints_inst.type,
            **(
                {"__new__": new(cls_.__new__)}
                if constraints_inst.type in {str, bytes, int, float}
                else {"__init__": init(cls_.__init__)}
            ),
        )
        cls: Type[ObjectT] = cast(Type[ObjectT], type(cls_.__name__, bases, cdict))

        return cls

    return constr_wrapper(_klass) if _klass else constr_wrapper


def _resolve_from_env(
    cls: Type[ObjectT],
    prefix: str,
    case_sensitive: bool,
    aliases: Mapping[str, str],
    *,
    environ: Mapping[str, str] = None,
) -> Type[ObjectT]:
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
            field.default_factory = lambda x=val: x
            field.default = dataclasses.MISSING
        else:
            field.default = val
            field.default_factory = dataclasses.MISSING
        setattr(cls, attr, field)

    return cls


def settings(
    _klass: Type[ObjectT] = None,
    *,
    prefix: str = "",
    case_sensitive: bool = False,
    frozen: bool = True,
    aliases: Mapping = None,
) -> Type[ObjectT]:
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
        cls = wrap_cls(dataclasses.dataclass(_cls, frozen=frozen), jsonschema=False)
        return cls

    return settings_wrapper(_klass) if _klass is not None else settings_wrapper


@functools.lru_cache(maxsize=None)
def schema(obj: Type[ObjectT], *, primitive: bool = False) -> ObjectSchemaField:
    """Get a JSON schema for object for the given object.

    Parameters
    ----------
    obj
        The class for which you wish to generate a JSON schema
    primitive
        Whether to return an instance of :py:class:`typic.schema.ObjectSchemaField` or
        a "primitive" (dict object).

    Examples
    --------
    >>> import typic
    >>>
    >>> @typic.klass
    ... class Foo:
    ...     bar: str
    ...
    >>> typic.schema(Foo)
    ObjectSchemaField(title='Foo', description='Foo(bar: str)', properties={'bar': StrSchemaField()}, additionalProperties=False, required=('bar',))
    >>> typic.schema(Foo, primitive=True)
    {'type': 'object', 'title': 'Foo', 'description': 'Foo(bar: str)', 'properties': {'bar': {'type': 'string'}}, 'additionalProperties': False, 'required': ['bar'], 'definitions': {}}

    """
    if obj in {FunctionType, MethodType}:
        raise ValueError("Cannot build schema for function or method.")

    annotation = resolver.resolve(obj)
    schm = schema_builder.get_field(annotation)
    try:
        setattr(obj, SCHEMA_NAME, schm)
    except (AttributeError, TypeError):
        pass
    return schm.primitive() if primitive else schm
