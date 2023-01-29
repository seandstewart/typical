from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Hashable,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)

from typical.classes import slotted
from typical.compat import (
    DATACLASS_KW_ONLY,
    DATACLASS_MATCH_ARGS,
    DATACLASS_NATIVE_SLOTS,
)
from typical.core.annotations import ObjectT
from typical.core.interfaces import SerdeFlags
from typical.magic.typed import WrappedObjectT, wrap_cls
from typical.types import freeze

__all__ = (
    "field",
    "klass",
    "make_typedclass",
    "Field",
)


_df_slots = cast(Tuple[str, ...], dataclasses.Field.__slots__)  # type: ignore[attr-defined]
_field_slots: Tuple[str, ...] = _df_slots + (
    "exclude",
    "external_name",
)

_EMPTY_METADATA: Mapping[Hashable, Any] = MappingProxyType({})
FactoryT = Callable[[], ObjectT]


class Field(dataclasses.Field):
    """An extension of :py:class:`dataclasses.Field` which adds a few parameters.

    This class adds some flags for determining the serialization protocol.

    Examples:
        >>> from typical import magic
        >>>
        >>> @magic.klass
        ... class Foo:
        ...     bar: str = magic.field(name="Bar")
        ...     exc: str = magic.field(exclude=True)
        ...
        >>> Foo("foo", "exc").primitive()
        {'Bar': 'foo'}
    """

    __slots__ = _field_slots

    def __init__(
        self,
        *,
        default: Union[ObjectT, dataclasses._MISSING_TYPE],
        default_factory: Union[FactoryT, dataclasses._MISSING_TYPE],
        init: bool,
        repr: Any,
        hash: Optional[Any],
        compare: bool,
        metadata: Optional[Mapping[Hashable, Any]],
        exclude: bool = False,
        name: str = None,
        **kwargs,
    ):
        super(Field, self).__init__(
            default, default_factory, init, repr, hash, compare, metadata, **kwargs  # type: ignore
        )
        self.exclude = exclude
        self.external_name = name

    @classmethod
    def from_field(cls: Type["Field"], f: dataclasses.Field) -> "Field":
        kwargs = dict(
            default=f.default,
            default_factory=f.default_factory,  # type: ignore
            init=f.init,
            repr=f.repr,
            hash=f.hash,
            compare=f.compare,
            metadata=f.metadata,  # type: ignore
        )
        if DATACLASS_KW_ONLY:
            kwargs["kw_only"] = f.kw_only  # type: ignore

        tf = cls(**kwargs)  # type: ignore[arg-type]
        tf.name = f.name
        tf.type = f.type
        return tf


def field(
    default: Union[ObjectT, dataclasses._MISSING_TYPE] = dataclasses.MISSING,
    *,
    default_factory: Union[FactoryT, dataclasses._MISSING_TYPE] = dataclasses.MISSING,
    init: bool = True,
    repr: bool = True,
    hash: Any = None,
    compare: bool = True,
    metadata: Mapping[Hashable, Any] = None,
    exclude: bool = False,
    name: str = None,
    kw_only: bool = False,
) -> Field:
    kwargs = dict(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        exclude=exclude,
        name=name,
    )
    if DATACLASS_KW_ONLY:
        kwargs["kw_only"] = kw_only
    return Field(**kwargs)  # type: ignore


def make_typedclass(
    cls: Type[ObjectT],
    *,
    init: bool = True,
    repr: bool = True,
    eq: bool = True,
    order: bool = False,
    unsafe_hash: bool = False,
    frozen: bool = False,
    delay: bool = False,
    strict: bool = False,
    jsonschema: bool = False,
    slots: bool = False,
    kw_only: bool = False,
    match_args: bool = True,
    serde: SerdeFlags = None,
    always: bool = None,
) -> Type[WrappedObjectT[ObjectT]]:
    """A convenience function for generating a dataclass with type-coercion.

    Allows the user to create typed dataclasses on-demand from a base-class, i.e.::

        TypedClass = make_typedclass(UnTypedClass)

    The preferred method is via the `klass` decorator, however.

    See Also:
        - :py:func:`klass`
        - :py:func:`dataclasses.dataclass`
    """
    # Make the base dataclass.
    kwargs = dict(
        init=init,
        repr=repr,
        eq=eq,
        order=order,
        unsafe_hash=unsafe_hash,
        frozen=frozen,
    )
    if DATACLASS_KW_ONLY:
        kwargs["kw_only"] = kw_only
    if DATACLASS_MATCH_ARGS:
        kwargs["match_args"] = match_args
    if DATACLASS_NATIVE_SLOTS:
        dcls = dataclasses.dataclass(cls, **kwargs, slots=slots)  # type: ignore
    else:
        dcls = dataclasses.dataclass(cls, **kwargs)  # type: ignore
        if slots:
            dcls = slotted(dcls)

    fields = [
        f if isinstance(f, Field) else Field.from_field(f)
        for f in dataclasses.fields(dcls)
    ]
    field_names = freeze({f.name: f.external_name or f.name for f in fields})
    exclude = frozenset({f.name for f in fields if f.exclude})
    dcls.__typic_fields__ = (*fields,)
    serde = serde or SerdeFlags()
    serde = serde.merge(SerdeFlags(fields=field_names, exclude=exclude))  # type: ignore
    return wrap_cls(
        cast("Type[ObjectT]", dcls),
        strict=strict,
        schema=jsonschema,
        serde=serde,
        always=always,
    )


@overload
def klass(_cls: Type[ObjectT]) -> Type[WrappedObjectT[ObjectT]]:
    ...


@overload
def klass(
    *,
    init: bool = True,
    repr: bool = True,
    eq: bool = True,
    order: bool = False,
    unsafe_hash: bool = False,
    frozen: bool = False,
    delay: bool = False,
    strict: bool = False,
    jsonschema: bool = True,
    slots: bool = False,
    kw_only: bool = False,
    match_args: bool = True,
    serde: SerdeFlags = None,
    always: bool = None,
) -> Callable[[Type[ObjectT]], Type[WrappedObjectT[ObjectT]]]:
    ...


def klass(
    _cls=None,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    delay=False,
    strict=False,
    jsonschema=True,
    slots=False,
    kw_only=False,
    match_args=True,
    serde=None,
    always=None,
):
    """A convenience decorator for generating a dataclass with type-coercion.

    This::

        import typic

        @typic.klass
        class Foo:
            bar: str

    Is functionally equivalent to::

        import dataclasses
        import typic

        @typic.al
        @dataclasses.dataclass
        class Foo:
            bar: str

    See Also:
        - :py:func:`~typical.magic.typed.wrap_cls`
        - :py:func:`dataclasses.dataclass`
    """

    def typedclass_wrapper(cls_):
        return make_typedclass(
            cls=cls_,
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            delay=delay,
            strict=strict,
            jsonschema=jsonschema,
            slots=slots,
            kw_only=kw_only,
            match_args=match_args,
            serde=serde,
            always=always,
        )

    return typedclass_wrapper(_cls) if _cls else typedclass_wrapper
