from __future__ import annotations as a

import collections
import dataclasses
import functools
import inspect
import types
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typic.checks import isfrozendataclass
from typic.compat import Generic, lru_cache
from typic.core.annotations import ReadOnly, WriteOnly
from typic.core.constants import (
    ORIG_SETTER_NAME,
    SERDE_ATTR,
    SERDE_FLAGS_ATTR,
    TYPIC_ANNOS_NAME,
)
from typic.core.constraints import ConstrainedType, constrained
from typic.core.constraints.core.validators import ValidatorProtocol
from typic.core.interfaces import (
    Annotation,
    DeserializerT,
    FieldIteratorT,
    SerdeFlags,
    SerdeProtocol,
    SerdeProtocolsT,
    SerializerT,
    TranslatorT,
)
from typic.core.resolver import resolver
from typic.core.serde.binder import BoundArguments
from typic.core.serde.ser import SerializationValueError
from typic.core.strict import (
    STRICT_MODE,
    Strict,
    StrictModeT,
    StrictStrT,
    is_strict_mode,
    strict_mode,
)
from typic.core.strings import Case
from typic.env import Environ, EnvironmentTypeError, EnvironmentValueError
from typic.types import freeze
from typic.util import cached_signature, cached_type_hints

__all__ = (
    "Annotation",
    "bind",
    "BoundArguments",
    "Case",
    "constrained",
    "ConstrainedType",
    "decode",
    "encode",
    "environ",
    "EnvironmentTypeError",
    "EnvironmentValueError",
    "flags",
    "is_strict_mode",
    "iterate",
    "tojson",
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
    "SchemaReturnT",
    "SerdeFlags",
    "SerdeProtocol",
    "SerializationValueError",
    "Strict",
    "strict_mode",
    "StrictStrT",
    "transmute",
    "translate",
    "typed",
    "validate",
    "wrap",
    "wrap_cls",
    "WriteOnly",
)

ObjectT = TypeVar("ObjectT", bound=object)
SchemaGenT = Callable[[Type[ObjectT]], Any]


transmute = resolver.transmute
translate = resolver.translate
validate = resolver.validate
bind = resolver.bind
register = resolver.des.register
primitive = resolver.primitive
schemas = resolver.schemas.all
schema = resolver.schema
protocols = resolver.protocols
protocol = resolver.resolve
tojson = resolver.tojson
iterate = resolver.iterate
flags = SerdeFlags
encode = resolver.encode
decode = resolver.decode


_T = TypeVar("_T")
_Callable = TypeVar("_Callable", bound=Callable[..., Any])
_Func = TypeVar("_Func", bound=types.FunctionType)
_Type = TypeVar("_Type", bound=type)


class TypicObjectT(Generic[_T]):
    __serde__: SerdeProtocol[Type[_T]]
    __serde_flags__: SerdeFlags
    __serde_protocols__: SerdeProtocolsT
    __setattr_original__: Callable[[_T, str, Any], None]
    __typic_resolved__: bool
    __iter__: FieldIteratorT[_T]
    schema: SchemaGenT
    primitive: SerializerT[_T]
    transmute: DeserializerT[_T]
    translate: TranslatorT[_T]
    validate: ValidatorProtocol[_T]
    tojson: Callable[..., str]
    iterate: FieldIteratorT[_T]


WrappedObjectT = Union[TypicObjectT[_T], _T]


def wrap(
    func: _Callable, *, delay: bool = None, strict: StrictModeT = STRICT_MODE
) -> _Callable:
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
    if isinstance(delay, bool):
        warnings.warn(
            "The `delay` argument is no longer required and is deprecated. "
            "It will be removed in a future version.",
            category=DeprecationWarning,
        )
    protos = protocols(func, strict=cast(bool, strict))
    params = cached_signature(func).parameters
    enforcer = resolver.binder.get_enforcer(parameters=params, protocols=protos)

    @functools.wraps(func)
    def func_wrapper(*args, **kwargs):
        args, kwargs = enforcer(*args, **kwargs)
        return func(*args, **kwargs)

    return cast(_Callable, func_wrapper)


def _bind_proto(cls, proto: SerdeProtocol):
    for n, attr in (
        (SERDE_ATTR, proto),
        ("primitive", proto.primitive),
        ("tojson", proto.tojson),
        ("transmute", staticmethod(proto.transmute)),
        ("validate", staticmethod(proto.validate)),
        ("translate", proto.translate),
        ("encode", proto.encode),
        ("decode", staticmethod(proto.decode)),
        ("iterate", proto.iterate),
        ("__iter__", proto.iterate),
    ):
        setattr(cls, n, attr)


@lru_cache(maxsize=None)
def _resolve_class(
    cls: Type[ObjectT],
    *,
    strict: StrictModeT = STRICT_MODE,
    always: bool = None,
    jsonschema: bool = True,
    serde: SerdeFlags = None,
) -> Type[WrappedObjectT[ObjectT]]:
    # Build the namespace for the new class
    strict = cast(bool, strict)
    protos = protocols(cls, strict=strict)
    if hasattr(cls, SERDE_FLAGS_ATTR):
        pserde: SerdeFlags = getattr(cls, SERDE_FLAGS_ATTR)
        if isinstance(pserde, dict):
            pserde = SerdeFlags(**pserde)
        serde = pserde.merge(serde) if serde else pserde
    serde = serde or SerdeFlags()
    ns: Dict[str, Any] = {
        SERDE_FLAGS_ATTR: serde,
        TYPIC_ANNOS_NAME: protos,
    }
    frozen = isfrozendataclass(cls)
    always = False if frozen else always
    if always is None:
        warnings.warn(
            "Keyword `always` will default to `False` in a future version. "
            "You should update your code to either explicitly declare `always=True` "
            "or update your code to not assume values will be coerced when set.",
            category=UserWarning,
            stacklevel=5,
        )
        always = True
    if jsonschema:
        ns["schema"] = classmethod(schema)
        resolver.schemas.attach(cls)

    # Wrap the init if
    #   a) this is a "frozen" dataclass
    #   b) we only want to coerce on init.
    # N.B.: Frozen dataclasses don't use the native setattr and can't be updated.
    if always is False:
        ns["__init__"] = wrap(cls.__init__, strict=strict)
    # For 'always', create a new setattr that applies the protocol for a given attr
    else:
        trans = freeze({x: y.transmute for x, y in protos.items()})

        def setattr_typed(setter):
            @functools.wraps(setter)
            def __setattr_typed__(self, name, item, *, __trans=trans, __setter=setter):
                __setter(
                    self,
                    name,
                    __trans[name](item) if name in __trans else item,
                )

            return __setattr_typed__

        ns.update(
            **{
                ORIG_SETTER_NAME: _get_setter(cls),
                "__setattr__": setattr_typed(cls.__setattr__),
            }
        )

    for name, attr in ns.items():
        setattr(cls, name, attr)
    # Get the protocol
    proto: SerdeProtocol = resolver.resolve(cls, is_strict=strict)
    # Bind it to the new class
    _bind_proto(cls, proto)
    # Track resolution state.
    setattr(cls, "__typic_resolved__", True)
    return cast(Type[WrappedObjectT[ObjectT]], cls)


def wrap_cls(
    klass: Type[ObjectT],
    *,
    delay: bool = False,
    strict: StrictModeT = STRICT_MODE,
    jsonschema: bool = True,
    serde: SerdeFlags = SerdeFlags(),
    always: bool = None,
) -> Type[WrappedObjectT[ObjectT]]:
    """Wrap a class to automatically enforce type-coercion on init.

    Notes
    -----
    While `Coercer.wrap` will work with classes alone, it changes the signature of the
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

    def cls_wrapper(cls_: Type[ObjectT]) -> Type[WrappedObjectT[ObjectT]]:
        if isinstance(delay, bool):
            warnings.warn(
                "The `delay` argument is no longer required and is deprecated. "
                "It will be removed in a future version.",
                category=DeprecationWarning,
            )
        setattr(cls_, "__delayed__", False)
        return _resolve_class(
            cls_, strict=strict, jsonschema=jsonschema, serde=serde, always=always
        )

    wrapped: Type[WrappedObjectT[ObjectT]] = cls_wrapper(klass)
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


@overload
def typed(
    _cls_or_callable: _Type, *, delay: bool = False, strict: bool = None
) -> Type[WrappedObjectT[_Type]]:
    ...


@overload
def typed(
    _cls_or_callable: _Func, *, delay: bool = False, strict: bool = None
) -> _Func:
    ...


@overload
def typed(
    *, delay: bool = False, strict: bool = None
) -> Union[Callable[[_Type], Type[WrappedObjectT[_Type]]], Callable[[_Func], _Func]]:
    ...


def typed(
    _cls_or_callable=None,
    *,
    delay: bool = False,
    strict: bool = None,
    always: bool = None,
):
    """A convenience function which automatically selects the correct wrapper.

    Parameters
    ----------
    delay
        Optionally delay annotation resolution until first call.
    strict
        Turn on "validator mode": e.g. validate incoming data rather than coerce.
    always
        Whether classes should always coerce values on their attributes.

    Returns
    -------
    The target object, appropriately wrapped.
    """
    strict = STRICT_MODE if strict is None else strict  # type: ignore

    def _typed(obj: Union[Callable, Type[ObjectT]]):
        if inspect.isclass(obj):
            return wrap_cls(obj, delay=delay, strict=strict, always=always)  # type: ignore
        elif callable(obj):  # type: ignore
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
    warnings.warn(
        "Delayed type resolution is handled automatically as of v2.3.0. "
        "This function is now a no-op and will be removed in a future version.",
        category=DeprecationWarning,
    )


environ = Environ(resolver)


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


PrimitiveT = Union[Dict, List, str, int, bool]
SchemaPrimitiveT = Dict[str, PrimitiveT]
SchemaReturnT = Union[SchemaPrimitiveT, Any]
