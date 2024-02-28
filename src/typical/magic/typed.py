from __future__ import annotations

import functools
import inspect
import types
from typing import Any, Callable, Dict, Tuple, Type, TypeVar, Union, cast, overload

from typical.api import protocols, resolver
from typical.checks import isfrozendataclass
from typical.compat import Generic, lru_cache
from typical.constraints.core.validators import ValidatorProtocol
from typical.core.annotations import ObjectT
from typical.core.constants import (
    ORIG_SETTER_NAME,
    SERDE_ATTR,
    SERDE_FLAGS_ATTR,
    TYPIC_ANNOS_NAME,
)
from typical.core.interfaces import (
    DeserializerT,
    FieldIteratorT,
    PrimitiveT,
    SerdeFlags,
    SerdeProtocol,
    SerdeProtocolsT,
    SerializerT,
    TranslatorT,
)
from typical.core.strict import STRICT_MODE, StrictModeT
from typical.inspection import cached_signature
from typical.magic.schema import attach as attach_schema
from typical.magic.schema import schema as schema_factory
from typical.types.frozendict import freeze

__all__ = (
    "al",
    "typed",
    "wrap",
    "wrap_cls",
    "TypicObjectT",
    "WrappedObjectT",
)


def wrap(func: _Callable, *, strict: StrictModeT = STRICT_MODE) -> _Callable:
    """Wrap a callable to automatically enforce type-coercion.

    Args:
        func: The callable for which you wish to ensure type-safety

    Keyword Args:
        strict: Turn on "validator mode": e.g. validate incoming data rather than coerce.

    See Also:
        - :py:func:`inspect.signature`
        - :py:meth:`inspect.Signature.bind`
    """
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
        ("primitive", proto.serialize),
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
    always: bool = False,
    schema: bool = True,
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

    # Get the protocol
    proto: SerdeProtocol = resolver.resolve(cls, is_strict=strict, flags=serde)
    if schema:
        ns["schema"] = classmethod(functools.partial(schema_factory))
        attach_schema(proto.constraints.constraints)
    for name, attr in ns.items():
        setattr(cls, name, attr)
    # Bind it to the new class
    _bind_proto(cls, proto)
    # Track resolution state.
    return cast(Type[WrappedObjectT[ObjectT]], cls)


_default_flags = SerdeFlags()


@overload
def wrap_cls(klass: Type[ObjectT]) -> Type[WrappedObjectT[ObjectT]]: ...


@overload
def wrap_cls(
    *,
    strict: StrictModeT = STRICT_MODE,
    schema: bool = True,
    serde: SerdeFlags = _default_flags,
    always: bool = False,
) -> Callable[[], Type[WrappedObjectT[ObjectT]]]: ...


@overload
def wrap_cls(
    klass: Type[ObjectT],
    *,
    strict: StrictModeT = STRICT_MODE,
    schema: bool = True,
    serde: SerdeFlags = _default_flags,
    always: bool = False,
) -> Type[WrappedObjectT[ObjectT]]: ...


def wrap_cls(
    klass: Type[ObjectT] = None,
    *,
    strict: StrictModeT = STRICT_MODE,
    schema: bool = True,
    serde: SerdeFlags = _default_flags,
    always: bool = False,
):
    """Wrap a class to automatically enforce type-coercion on init.

    Args:
        klass: The class you wish to patch with coercion.
    Keyword Args:
        strict: Turn on "validator mode": e.g. validate incoming data rather than coerce.
        schema: Add a @classmethod for generating schemas for this class. Defaults `True`.
        serde: Optional settings for serialization/deserialization. Defaults `True`.
        always: Whether to coerce when setting attributes. Defaults `False`.
    """

    def cls_wrapper(cls_: Type[ObjectT]) -> Type[WrappedObjectT[ObjectT]]:
        return _resolve_class(
            cls_, strict=strict, schema=schema, serde=serde, always=always
        )

    if klass:
        return cls_wrapper(klass)

    return cls_wrapper


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
    *, strict: bool
) -> Callable[[_Type], Type[WrappedObjectT[_Type]]] | Callable[[_Func], _Func]: ...


@overload
def typed(_cls_or_callable: _Type) -> Type[WrappedObjectT[_Type]]: ...


@overload
def typed(_cls_or_callable: _Type, *, strict: bool) -> Type[WrappedObjectT[_Type]]: ...


@overload
def typed(_cls_or_callable: _Func) -> _Func: ...


@overload
def typed(_cls_or_callable: _Func, *, strict: bool) -> _Func: ...


def typed(
    _cls_or_callable=None,
    *,
    strict: bool = None,
    always: bool = False,
):
    """A convenience function which automatically selects the correct wrapper.

    Keyword Args:
        strict: Turn on "validator mode": e.g. validate incoming data rather than coerce.
        always: Whether classes should always coerce values on their attributes.
    """
    strict = STRICT_MODE if strict is None else strict  # type: ignore

    def _typed(obj: Union[Callable, Type[ObjectT]]):
        if inspect.isclass(obj):
            return wrap_cls(obj, strict=strict, always=always)  # type: ignore
        elif callable(obj):  # type: ignore
            return wrap(obj, strict=strict)  # type: ignore
        else:
            raise TypeError(
                f"{__name__} requires a callable or class. Provided: {type(obj)}: {obj}"
            )

    return _typed(_cls_or_callable) if _cls_or_callable is not None else _typed


al = typed


_T = TypeVar("_T")


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
SchemaPrimitiveT = Dict[str, PrimitiveT]
SchemaReturnT = Union[SchemaPrimitiveT, Any]
SchemaGenT = Callable[[Type[ObjectT]], Any]


_Callable = TypeVar("_Callable", bound=Callable[..., Any])
_Func = TypeVar("_Func", bound=types.FunctionType)
_Type = TypeVar("_Type", bound=type)
