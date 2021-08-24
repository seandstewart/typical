from __future__ import annotations

import dataclasses
import inspect
import reprlib
import sys
import warnings
from types import FrameType
from typing import (
    Callable,
    Union,
    Type,
    Any,
    Tuple,
    Mapping,
    Deque,
    Optional,
    Dict,
    Iterable,
    cast,
    TypeVar,
    AnyStr,
    Iterator,
    TYPE_CHECKING,
    Generic,
)

from typic import strict as st, util, constraints as const
from typic.checks import isclassvartype
from typic.common import AnyOrTypeT, Case, EMPTY, ObjectT, OriginT
from typic.compat import TypedDict, ForwardRef, evaluate_forwardref, Protocol
from typic.types import freeze

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class SerdeProtocol(Generic[OriginT]):
    """An actionable run-time serialization & deserialization protocol for a type."""

    annotation: Annotation[Type[OriginT]]
    """The target annotation and various meta-data."""
    constraints: Optional[const.ConstraintsProtocolT[OriginT]]
    """Type restriction configuration, if any."""
    deserialize: DeserializerT[OriginT] = dataclasses.field(repr=False)
    """The callable to deserialize data into the annotation."""
    decode: DecoderT[OriginT] = dataclasses.field(repr=False)
    """Decode an input from the on-the-wire format to the annotation."""
    serialize: SerializerT[OriginT] = dataclasses.field(repr=False)
    """The callable to serialize an instance of the annotation."""
    encode: EncoderT[OriginT] = dataclasses.field(repr=False)
    """Encode an instance of the annotation into the provided on-the-wire format."""
    validate: const.ValidateT[OriginT] = dataclasses.field(repr=False)
    """Validate an input against the annotation."""
    translate: TranslatorT[OriginT] = dataclasses.field(repr=False)
    """Translate an instance of the annotation into another type."""
    iterate: FieldIteratorT = dataclasses.field(repr=False)
    """Iterate over an instance of the annotation, if possible."""
    tojson: EncoderT[OriginT] = dataclasses.field(repr=False)
    """Dump an instance of the annotation to valid JSON."""
    transmute: DeserializerT[OriginT] = dataclasses.field(repr=False, init=False)
    """Transmute an input into the annotation."""
    primitive: SerializerT[OriginT] = dataclasses.field(repr=False, init=False)
    """Get the "primitive" representation of the annotation."""

    def __post_init__(self):
        # Pin the transmuter and the primitiver
        self.transmute = self.deserialize
        self.primitive = self.serialize

    def __call__(self, val: ObjectT) -> OriginT:
        return self.transmute(val)  # type: ignore


_OutputT = TypeVar("_OutputT", covariant=True)
_InputT = TypeVar("_InputT", contravariant=True)


class EncoderT(Protocol[_InputT]):
    """The signature of an on-the-wire encoder for an output."""

    __name__: str
    __qualname__: str

    def __call__(self, value: _InputT, **kwargs) -> AnyStr:
        ...


class DecoderT(Protocol[_OutputT]):
    """The signature of an on-the-wire decoder for an input."""

    __name__: str
    __qualname__: str

    def __call__(self, value: AnyStr, **kwargs) -> _OutputT:
        ...


class TranslatorT(Protocol[_InputT]):
    """The signature of a type translator pinned to the origin type of `InputT`."""

    __name__: str
    __qualname__: str

    def __call__(self, value: _InputT, target: Type[_OutputT]) -> _OutputT:
        ...


class SerializerT(Protocol[_InputT]):
    """The signature of a type serializer."""

    __name__: str
    __qualname__: str

    def __call__(
        self, obj: _InputT, *, lazy: bool = False, name: util.ReprT = None
    ) -> Union[PrimitiveT, Iterator[PrimitiveT]]:
        ...


class DeserializerT(Protocol[_OutputT]):
    """The signature of a type deserializer."""

    __name__: str
    __qualname__: str

    def __call__(self, val: Any) -> _OutputT:
        ...


class FieldIteratorT(Protocol[_InputT]):
    """The type-signature for a FieldIterator function."""

    __name__: str
    __qualname__: str

    def __call__(
        self, o: _InputT, *, values: bool = False, **kwargs
    ) -> Iterator[Union[Tuple[str, Any], Any]]:
        ...


PrimitiveT = TypeVar("PrimitiveT", str, int, float, list, dict)
""""""
OmitSettingsT = Tuple[AnyOrTypeT, ...]
"""Specify types or values which you wish to omit from the output."""
FieldSerializersT = Mapping[str, SerializerT]
"""A mapping of field names to their serializer functions."""
FieldDeserializersT = Mapping[str, DeserializerT]
"""A mapping of field names to their deserializer functions."""

DeserializerTypeCheckT = Callable[[Type[Any]], bool]
"""A type alias for the expected signature of a type-check for a coercer.

Type-checkers should return a boolean indicating whether the provided type is valid for
a given coercer.
"""
DeserializerRegistryT = Deque[Tuple[DeserializerTypeCheckT, DeserializerT]]
"""A stack of potential deserializers and their function identifiers."""

FieldSettingsT = Union[Tuple[str, ...], Mapping[str, str]]
"""An iterable of fields to ensure are included on *out* and retrieved on *in*

A mapping should be of attribute name -> out/in field name.
"""


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class SerdeFlags:
    """Optional settings for a Ser-ialization/de-serialization protocol."""

    signature_only: bool = False
    """Restrict the output of serialization to the class signature."""
    case: Optional[Case] = None
    """Select the case-style for the input/output fields."""
    omit: Optional[OmitSettingsT] = None
    """Provide a tuple of types or values which should be omitted on serialization."""
    fields: Optional[FieldSettingsT] = None
    """Ensure a set of fields are included in the output.

    If given a mapping, provide a mapping to the output field name.
    """
    exclude: Optional[Iterable[str]] = None
    """Provide a set of fields which will be excluded from the output."""
    encoder: Optional[EncoderT] = None
    """Provide a callable which can encode your data to a bytes/binary output."""
    decoder: Optional[DecoderT] = None
    """Provide a callable with can decode a bytes/binary input for deserialization."""

    def __init__(
        self,
        *,
        signature_only: bool = False,
        case: Case = None,
        omit: OmitSettingsT = None,
        fields: FieldSettingsT = None,
        exclude: Iterable[str] = None,
        encoder: EncoderT = None,
        decoder: DecoderT = None,
    ):
        self.signature_only = signature_only
        self.case = case
        self.omit = freeze(omit)  # type: ignore
        self.fields = cast(FieldSettingsT, freeze(fields)) or ()
        self.exclude = cast(Iterable[str], freeze(exclude)) or ()
        self.encoder = encoder
        self.decoder = decoder

    def merge(self, other: "SerdeFlags") -> "SerdeFlags":
        """Merge the values of another SerdeFlags instance into this one."""
        case = other.case or self.case
        signature_only = self.signature_only or other.signature_only
        if other.omit and self.omit:
            omit = (*self.omit, *(o for o in other.omit if o not in self.omit))
        else:
            omit = other.omit or self.omit  # type: ignore

        if other.fields and self.fields:
            if not isinstance(other.fields, Mapping):
                other.fields = freeze({x: x for x in other.fields})  # type: ignore
            if not isinstance(self.fields, Mapping):
                self.fields = freeze({x: x for x in self.fields})  # type: ignore
            fields = {**self.fields, **other.fields}  # type: ignore
        else:
            fields = other.fields or self.fields  # type: ignore

        if other.exclude and self.exclude:
            exclude = {*self.exclude, *other.exclude}
        else:
            exclude = other.exclude or self.exclude  # type: ignore
        encoder = other.encoder or self.encoder
        decoder = other.decoder or self.decoder
        return SerdeFlags(
            signature_only=signature_only,
            case=case,
            omit=omit,
            fields=fields,
            exclude=exclude,
            encoder=encoder,
            decoder=decoder,
        )


class SerdeConfigD(TypedDict):
    fields: Mapping[str, "AnnotationT"]
    fields_out: Mapping[str, str]
    fields_in: Mapping[str, str]
    fields_getters: Mapping[str, Callable[[str], Any]]
    omit_values: Tuple[Any, ...]
    encoder: Optional[EncoderT]
    decoder: Optional[DecoderT]


@util.slotted
@dataclasses.dataclass
class SerdeConfig:
    flags: SerdeFlags = dataclasses.field(default_factory=SerdeFlags)
    fields: Mapping[str, Annotation] = dataclasses.field(default_factory=dict)
    fields_out: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_in: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_getters: Mapping[str, Callable[[str], Any]] = dataclasses.field(
        default_factory=dict
    )
    omit_values: Tuple[Any, ...] = dataclasses.field(default_factory=tuple)
    encoder: Optional[EncoderT] = None
    decoder: Optional[DecoderT] = None

    def __hash__(self):
        return hash(f"{self}")

    @reprlib.recursive_repr()
    def __repr__(self) -> str:
        fs = []
        for field in dataclasses.fields(self):
            fs.append(f"{field.name}={getattr(self, field.name)!r}")
        return f"{self.__class__.__name__}({', '.join(fs)})"

    def asdict(self) -> SerdeConfigD:
        return SerdeConfigD(
            fields=self.fields,
            fields_out=self.fields_out,
            fields_in=self.fields_in,
            fields_getters=self.fields_getters,
            omit_values=self.omit_values,
            encoder=self.encoder,
            decoder=self.decoder,
        )


_AT = TypeVar("_AT")


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class Annotation(Generic[_AT]):
    """The resolved, actionable annotation for a given annotation."""

    EMPTY = EMPTY

    resolved: _AT
    """The type annotation used to build the coercer."""
    origin: Type
    """The "origin"-type of the original annotation.

    Notes
    -----
    This is not necessarily the "origin"-type of the ``annotation`` attribute.
    """
    un_resolved: Any
    """The type annotation before resolving super-types."""
    parameter: inspect.Parameter
    """The parameter this annotation refers to."""
    translator: TranslatorT[_AT] = dataclasses.field(init=False)
    """A factory for generating a translation protocol between higher-level types."""
    optional: bool = False
    """Whether this annotation allows null/default values."""
    strict: st.StrictModeT = st.STRICT_MODE
    """Whether to enforce the annotation, rather than coerce."""
    static: bool = True
    """Whether we may compile a protocol ahead of time for an annotation."""
    serde: SerdeConfig = dataclasses.field(default_factory=SerdeConfig)
    """The configuration for serializing and deserializing the given type."""
    constraints: Optional["const.ConstraintsT"] = None
    """Type restriction configuration, if any."""
    generic: Type = dataclasses.field(init=False)
    has_default: bool = dataclasses.field(init=False)
    is_class_var: bool = dataclasses.field(init=False)
    resolved_origin: _AT = dataclasses.field(init=False)
    args: Tuple[Type, ...] = dataclasses.field(init=False)

    def __post_init__(self):
        self.has_default = self.parameter.default is not self.EMPTY
        self.args = util.get_args(self.resolved)
        self.resolved_origin = util.origin(self.resolved)
        self.generic = getattr(self.resolved, "__origin__", self.resolved_origin)
        self.is_class_var = isclassvartype(self.un_resolved)


_empty = object()


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class ForwardDelayedAnnotation:
    ref: ForwardRef
    module: str
    resolver: "Resolver"
    parameter: Optional[inspect.Parameter] = None
    is_optional: Optional[bool] = None
    is_strict: Optional[st.StrictModeT] = None
    flags: Optional["SerdeFlags"] = None
    default: Any = _empty
    frame: Optional[FrameType] = dataclasses.field(default=None, hash=False)
    _name: Optional[str] = None
    _resolved: Optional["SerdeProtocol"] = dataclasses.field(default=None)

    @reprlib.recursive_repr()
    def __repr__(self):
        return (
            f"{self.__class__}("
            f"ref={self.ref},"
            f"module={self.module}!r, "
            f"parameter={self.parameter}, "
            f"is_optional={self.is_optional}, "
            f"is_strict={self.is_strict}, "
            f"flags={self.flags}, "
            f"default={self.default})"
        )

    @property
    def resolved(self):
        if self._resolved is None:
            globalns = sys.modules[self.module].__dict__.copy()
            try:
                type = evaluate_forwardref(self.ref, globalns, globalns)
            except NameError as e:
                name = self.ref.__forward_arg__
                type = util.extract(name, frame=self.frame)
                if not type:
                    warnings.warn(
                        f"Couldn't resolve forward reference: {e}. "
                        f"Make sure this type is available in {self.module}."
                    )
                    type = Any
            anno = self.resolver.annotation(
                type,
                name=self._name,
                parameter=self.parameter,
                is_optional=self.is_optional,
                is_strict=self.is_strict,
                flags=self.flags,
                default=EMPTY if self.default is _empty else self.default,
            )
            self._resolved = self.resolver._resolve_from_annotation(anno)
        return self._resolved

    @property
    def name(self) -> str:
        return util.get_name(self.ref)


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class DelayedAnnotation:
    type: Type
    resolver: Resolver
    parameter: Optional[inspect.Parameter] = None
    is_optional: Optional[bool] = None
    is_strict: Optional[st.StrictModeT] = None
    flags: Optional["SerdeFlags"] = None
    default: Any = _empty
    _name: Optional[str] = None
    _resolved: Optional["SerdeProtocol"] = dataclasses.field(default=None)

    @reprlib.recursive_repr()
    def __repr__(self):
        return (
            f"{self.__class__}("
            f"parameter={self.parameter}, "
            f"is_optional={self.is_optional}, "
            f"is_strict={self.is_strict}, "
            f"flags={self.flags}, "
            f"default={self.default})"
        )

    @property
    def resolved(self):
        if self._resolved is None:
            anno = self.resolver.annotation(
                self.type,
                name=self._name,
                parameter=self.parameter,
                is_optional=self.is_optional,
                is_strict=self.is_strict,
                flags=self.flags,
                default=EMPTY if self.default is _empty else self.default,
            )
            self._resolved = self.resolver._resolve_from_annotation(anno)
        return self._resolved

    @property
    def origin(self):
        return self.type

    @property
    def name(self) -> str:
        return util.get_name(self.type)


AnnotationT = Union[Annotation, DelayedAnnotation, ForwardDelayedAnnotation]


class DelayedSerdeProtocol(SerdeProtocol):
    __slots__ = (
        "delayed",
        "_resolved",
    )

    def __init__(
        self,
        delayed: Union[ForwardDelayedAnnotation, DelayedAnnotation],
    ):
        self.delayed = delayed
        self.transmute = lambda val: self.deserialize(val)  # type: ignore
        self._resolved = False

    def __repr__(self):
        return f"{self.__class__.__name__}(delayed={self.delayed}, resolved={self._resolved})"

    def __delayed_init__(self):
        if self._resolved:
            return
        protocol = self.delayed.resolved
        super().__init__(
            annotation=protocol.annotation,
            constraints=protocol.constraints,
            deserialize=protocol.deserialize,
            decode=protocol.decode,
            serialize=protocol.serialize,
            encode=protocol.encode,
            validate=protocol.validate,
            translate=protocol.translate,
            iterate=protocol.iterate,
            tojson=protocol.tojson,
        )
        self._resolved = True

    def __getattr__(self, item):
        self.__delayed_init__()
        return super().__getattribute__(item)

    def __call__(self, val: Any) -> ObjectT:
        return self.transmute(val)  # type: ignore


SerdeProtocolsT = Dict[str, SerdeProtocol]
"""A mapping of attr/param name to :py:class:`SerdeProtocol`."""


class _Unprocessed:
    def __repr__(self):
        return "<unprocessed>"


Unprocessed = _Unprocessed()


class _Omit:
    def __repr__(self):
        return "<omit>"


Omit = _Omit()
KT = TypeVar("KT")
VT = TypeVar("VT")
KVPairT = Tuple[KT, VT]
