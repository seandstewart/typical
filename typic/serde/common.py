import dataclasses
import inspect
import reprlib
import sys
import warnings
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
)

from typic import strict as st, util, constraints as const
from typic.common import AnyOrTypeT, Case, EMPTY, ObjectT
from typic.compat import TypedDict, ForwardRef, evaluate_forwardref
from typic.ext import json
from typic.types import freeze

if TYPE_CHECKING:
    from .resolver import Resolver


OmitSettingsT = Tuple[AnyOrTypeT, ...]
"""Specify types or values which you wish to omit from the output."""
SerializerT = Union[Callable[[Any, bool, str], Any], Callable[[Any], Any]]
"""The signature of a type serializer."""
DeserializerT = Callable[[Any], Any]
"""The signature of a type deserializer."""
TranslatorT = Callable[[Any], Any]
"""The signature of a type translator."""
FieldIteratorT = Callable[[Any], Iterator[Union[Tuple[str, Any], Any]]]
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


@util.slotted
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

    def __init__(
        self,
        signature_only: bool = False,
        case: Case = None,
        omit: OmitSettingsT = None,
        fields: FieldSettingsT = None,
        exclude: Iterable[str] = None,
    ):
        self.signature_only = signature_only
        self.case = case
        self.omit = freeze(omit)  # type: ignore
        self.fields = cast(FieldSettingsT, freeze(fields))
        self.exclude = cast(Iterable[str], freeze(exclude))

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
        return SerdeFlags(
            signature_only=signature_only,
            case=case,
            omit=omit,
            fields=fields,
            exclude=exclude,
        )


class SerdeConfigD(TypedDict):
    fields: Mapping[str, "AnnotationT"]
    fields_out: Mapping[str, str]
    fields_in: Mapping[str, str]
    fields_getters: Mapping[str, Callable[[str], Any]]
    omit_values: Tuple[Any, ...]


@util.slotted
@dataclasses.dataclass
class SerdeConfig:
    flags: SerdeFlags = dataclasses.field(default_factory=SerdeFlags)
    fields: Mapping[str, "AnnotationT"] = dataclasses.field(default_factory=dict)
    fields_out: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_in: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_getters: Mapping[str, Callable[[str], Any]] = dataclasses.field(
        default_factory=dict
    )
    omit_values: Tuple[Any, ...] = dataclasses.field(default_factory=tuple)

    def __hash__(self):
        return hash(f"{self}")

    def asdict(self) -> SerdeConfigD:
        return SerdeConfigD(
            fields=self.fields,
            fields_out=self.fields_out,
            fields_in=self.fields_in,
            fields_getters=self.fields_getters,
            omit_values=self.omit_values,
        )


_T = TypeVar("_T")


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class Annotation:
    """The resolved, actionable annotation for a given annotation."""

    EMPTY = EMPTY

    resolved: Any
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
    translator: "TranslatorT" = dataclasses.field(init=False)
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
    resolved_origin: Type = dataclasses.field(init=False)
    args: Tuple[Type, ...] = dataclasses.field(init=False)

    def __post_init__(self):
        self.has_default = self.parameter.default is not self.EMPTY
        self.args = util.get_args(self.resolved)
        self.resolved_origin = util.origin(self.resolved)
        self.generic = getattr(self.resolved, "__origin__", self.resolved_origin)


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
    localns: Optional[Mapping] = dataclasses.field(hash=False, default=None)
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
                type = evaluate_forwardref(self.ref, globalns or {}, self.localns or {})
            except NameError as e:
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
    resolver: "Resolver"
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


@util.slotted(dict=False)
@dataclasses.dataclass(unsafe_hash=True)
class SerdeProtocol:
    """An actionable run-time serialization & deserialization protocol for a type."""

    annotation: Annotation
    """The target annotation and various meta-data."""
    deserializer: Optional[DeserializerT] = dataclasses.field(repr=False)
    """The deserializer for the annotation."""
    serializer: Optional[SerializerT] = dataclasses.field(repr=False)
    """The serializer for the given annotation."""
    constraints: Optional[const.ConstraintsT]
    """Type restriction configuration, if any."""
    validator: Optional[const.ValidatorT] = dataclasses.field(repr=False)
    """The type validator, if any"""
    validate: const.ValidatorT = dataclasses.field(init=False)
    """Validate an input against the annotation."""
    transmute: DeserializerT = dataclasses.field(init=False)
    """Transmute an input into the annotation."""
    primitive: SerializerT = dataclasses.field(init=False)
    """Get the "primitive" representation of the annotation."""
    tojson: Callable[..., AnyStr] = dataclasses.field(init=False)
    translate: TranslatorT = dataclasses.field(init=False)

    def __post_init__(self):
        # Pass through if for some reason there's no coercer.
        deserialize = self.deserializer or (lambda o: o)
        # Set the validator
        self.validate: const.ValidatorT = self.validator or (lambda o: o)
        # Pin the transmuter and the primitiver
        self.transmute = deserialize
        self.primitive = self.serializer or (lambda o, lazy=False, name=None: o)

        def _json(
            val: ObjectT,
            *,
            indent: int = 0,
            ensure_ascii: bool = False,
            __prim=self.primitive,
            __dumps=json.dumps,
            **kwargs,
        ) -> str:
            return __dumps(
                __prim(val, lazy=True),
                indent=indent,
                ensure_ascii=ensure_ascii,
                **kwargs,
            )

        _json.__name__ = "tojson"
        _json.__qualname__ = f"{self.__class__}.{_json.__name__}"
        _json.__module__ = self.__class__.__module__
        self.tojson = _json

        def translate(
            val: Any, target: Type[_T], *, __factory=self.annotation.translator
        ) -> _T:
            trans = __factory(target)
            return trans(val)

        self.translate = translate

    def __call__(self, val: Any) -> ObjectT:
        return self.transmute(val)  # type: ignore


class DelayedSerdeProtocol(SerdeProtocol):
    __slots__ = ("delayed", "_protocol",) + tuple(SerdeProtocol.__slots__)

    def __init__(
        self, delayed: Union[ForwardDelayedAnnotation, DelayedAnnotation],
    ):
        self.delayed = delayed
        self._protocol: Optional[SerdeProtocol] = None
        self.transmute = lambda val: self.proto.transmute(val)  # type: ignore

    def __repr__(self):
        return f"{self.__class__.__name__}(delayed={self.delayed}, protocol={self._protocol})"

    @property
    def proto(self) -> SerdeProtocol:
        if self._protocol is None:
            _protocol = self.delayed.resolved
            for name in SerdeProtocol.__slots__:
                object.__setattr__(self, name, getattr(_protocol, name))
            self._protocol = _protocol
        return self._protocol

    def __getattr__(self, item):
        return self.proto.__getattribute__(item)

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
