import dataclasses
import inspect
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
)

from typic import strict as st, util, constraints as const
from typic.common import AnyOrTypeT, Case, EMPTY, ObjectT
from typic.compat import TypedDict
from typic.ext import json
from typic.types import freeze
from .translator import translator


OmitSettingsT = Tuple[AnyOrTypeT, ...]
"""Specify types or values which you wish to omit from the output."""
SerializerT = Union[Callable[[Any, bool], Any], Callable[[Any], Any]]
"""The signature of a type serializer."""
DeserializerT = Callable[[Any], Any]
"""The signature of a type deserializer."""
TranslatorT = Callable[[Any], Any]
"""The signature of a type translator."""
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


class SerdeConfigD(TypedDict):
    fields: Mapping[str, "Annotation"]
    fields_out: Mapping[str, str]
    fields_in: Mapping[str, str]
    fields_getters: Mapping[str, Callable[[str], Any]]
    omit_values: Tuple[Any, ...]


@dataclasses.dataclass
class SerdeConfig:
    flags: SerdeFlags = dataclasses.field(default_factory=SerdeFlags)
    fields: Mapping[str, "Annotation"] = dataclasses.field(default_factory=dict)
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

    @property
    def has_default(self) -> bool:
        """Whether or not the annotation has a defined default value."""
        return self.parameter.default is not self.EMPTY

    @property
    def args(self) -> Tuple[Any, ...]:
        """What types are subscripted to this annotation, if any."""
        return util.get_args(self.resolved)

    def translator(self, target: Type[_T]) -> TranslatorT:
        """A factory for translating from this type to another."""
        t = translator.factory(self, target)
        return t


@dataclasses.dataclass(unsafe_hash=True)
class SerdeProtocol:
    """An actionable run-time serialization & deserialization protocol for a type."""

    annotation: Annotation
    """The target annotation and various meta-data."""
    deserializer: Optional[DeserializerT]
    """The coercer for the annotation."""
    serializer: Optional[SerializerT]
    """The serializer for the given annotation."""
    constraints: Optional[const.ConstraintsT]
    """Type restriction configuration, if any."""
    validator: Optional[const.ValidatorT]
    """The type validator, if any"""

    def __post_init__(self):
        # Pass through if for some reason there's no coercer.
        self.deserialize = self.deserializer or (lambda o: o)
        # Set the validator
        self.validate = self.validator or (lambda o: o)
        # Pin the transmuter and the primitiver
        self.transmute = self.deserialize
        self.primitive = self.serializer or (lambda o, lazy=False: o)

        def _json(
            val: ObjectT,
            *,
            indent: int = 0,
            ensure_ascii: bool = False,
            __prim=self.primitive,
        ) -> str:
            return json.dumps(
                __prim(val, lazy=True), indent=indent, ensure_ascii=ensure_ascii
            )

        self.tojson = _json

        def translate(
            val: Any, target: Type[_T], *, __factory=self.annotation.translator
        ) -> _T:
            trans = __factory(target)
            return trans(val)

        self.translate = translate

    def __call__(self, val: Any) -> ObjectT:
        return self.transmute(val)


SerdeProtocolsT = Dict[str, SerdeProtocol]
"""A mapping of attr/param name to :py:class:`SerdeProtocol`."""
