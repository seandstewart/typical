import abc
import dataclasses
import datetime
import decimal
import enum
import functools
import inspect
import ipaddress
import pathlib
import re
import uuid
from collections.abc import Mapping as Mapping_abc, Collection as Collection_abc
from functools import partial
from operator import attrgetter, methodcaller
from types import MappingProxyType
from typing import (
    Type,
    Optional,
    Callable,
    Collection,
    Union,
    Tuple,
    Mapping,
    Any,
    ClassVar,
    cast,
)

import inflection

from typic import util, checks, api, gen, types
from typing_extensions import TypedDict

__all__ = (
    "AnyOrTypeT",
    "FieldSerializersT",
    "FieldSettingsT",
    "OmitSettingsT",
    "Case",
    "DEFAULT_ENCODING",
    "primitive",
    "SerializerT",
    "SerdeFlags",
    "Serde",
)


NameTransformerT = Callable[[str], str]


class Case(str, enum.Enum):
    """An enumeration of the supported case-styles for field names."""

    CAMEL = "camelCase"
    SNAKE = "snake_case"
    PASCAL = "PascalCase"
    KEBAB = "kebab-case"
    DOT = "dot.case"

    @property
    def transformer(self) -> NameTransformerT:

        return _TRANSFORMERS[self]


_TRANSFORMERS = {
    Case.CAMEL: partial(inflection.camelize, uppercase_first_letter=False),
    Case.SNAKE: inflection.underscore,
    Case.PASCAL: inflection.camelize,
    Case.KEBAB: inflection.dasherize,
    Case.DOT: partial(inflection.parameterize, separator="."),
}
DEFAULT_ENCODING = "utf-8"

AnyOrTypeT = Union[Type, Any]
FieldSettingsT = Union[Tuple[str, ...], Mapping[str, str]]
"""Specify the fields to include.

Optionally map to an alternative name for output.
"""
OmitSettingsT = Tuple[AnyOrTypeT, ...]
"""Specify types or values which you wish to omit from the output."""
SerializerT = Callable[[Any], Any]
"""The signature of a type serializer."""
DeserializerT = Callable[[Any], Any]
"""The signature of a type deserializer."""
FieldSerializersT = Mapping[str, SerializerT]
"""A mapping of field names to their serializer functions."""
FieldDeserializersT = Mapping[str, DeserializerT]
"""A mapping of field names to their deserializer functions."""


def _decode(o) -> str:
    return o.decode(DEFAULT_ENCODING)


def _iso(o) -> str:
    if isinstance(o, (datetime.datetime, datetime.time)) and not o.tzinfo:
        return f"{o.isoformat()}+00:00"
    return o.isoformat()


_total_secs = methodcaller("total_seconds")
_pattern = attrgetter("pattern")


class SerdeConfigD(TypedDict):
    fields_ser: FieldSerializersT
    fields_deser: FieldDeserializersT
    fields_out: Mapping[str, str]
    fields_in: Mapping[str, str]
    fields_getters: Mapping[str, Callable[[str], Any]]
    fields_case: Optional[Case]
    omit_values: Tuple[Any, ...]


@dataclasses.dataclass
class SerdeConfig:
    fields_ser: FieldSerializersT = dataclasses.field(default_factory=dict)
    fields_deser: FieldDeserializersT = dataclasses.field(default_factory=dict)
    fields_out: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_in: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_getters: Mapping[str, Callable[[str], Any]] = dataclasses.field(
        default_factory=dict
    )
    fields_case: Optional[Case] = None
    omit_values: Tuple[Any, ...] = dataclasses.field(default_factory=tuple)

    def asdict(self) -> SerdeConfigD:
        return SerdeConfigD(
            fields_ser=self.fields_ser,
            fields_deser=self.fields_deser,
            fields_out=self.fields_out,
            fields_in=self.fields_in,
            fields_getters=self.fields_getters,
            fields_case=self.fields_case,
            omit_values=self.omit_values,
        )


class SerdeFactory:
    """A factory for generating high-performance serializers/deserializers.

    Notes
    -----
    Should not be used directly.
    """

    _DEFINED: Mapping[Type, Callable[[Any], Any]] = {
        ipaddress.IPv4Address: str,
        ipaddress.IPv4Network: str,
        ipaddress.IPv6Address: str,
        ipaddress.IPv6Interface: str,
        ipaddress.IPv6Network: str,
        re.Pattern: _pattern,  # type: ignore
        pathlib.Path: str,
        types.AbsoluteURL: str,
        types.DSN: str,
        types.DirectoryPath: str,
        types.Email: str,
        types.FilePath: str,
        types.HostName: str,
        types.NetworkAddress: str,
        types.RelativeURL: str,
        types.SecretBytes: lambda o: _decode(o.secret),
        types.SecretStr: attrgetter("secret"),
        types.URL: str,
        uuid.UUID: str,
        decimal.Decimal: float,
        bytes: _decode,
        bytearray: _decode,
        datetime.date: _iso,
        datetime.datetime: _iso,
        datetime.time: _iso,
        datetime.timedelta: _total_secs,
    }

    _LISTITER = (list, tuple, set, frozenset, Collection, Collection_abc)
    _DICTITER = (dict, Mapping, Mapping_abc, MappingProxyType, types.FrozenDict)
    _PRIMITIVES = (str, int, bool, float, type(None))
    _DYNAMIC = frozenset(
        {Union, Any, inspect.Parameter.empty, dataclasses.MISSING, ClassVar}
    )

    def _extract_arg(self, t: Type) -> Optional[Type]:
        args = util.get_args(t)
        if len(args) in {1, 2}:
            return args[0]
        return None

    def _get_name(self, serdes: "Serde", *, tail: str = "serializer") -> str:
        return re.sub(r"\W+", "_", f"{serdes.type}_{tail}")

    def _compile_list_serializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> SerializerT:
        # Check for value types
        args = util.get_args(serdes.type)
        arg_ser: Optional[SerializerT] = None
        if args:
            arg_serdes: "Serde" = dataclasses.replace(serdes, type=args[0])
            arg_ser = arg_serdes.serializer
        # Get the important names
        func_name = self._get_name(serdes)
        anno_name = f"{func_name}_anno"
        arg_ser_name = f"{func_name}_arg_ser"
        # Build the namespace
        ns = {anno_name: serdes.type, arg_ser_name: arg_ser}
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o")) as func:
                # Call the serializer for the value if it exists
                x = f"{arg_ser_name}(x)" if arg_ser else "x"
                # Write the line.
                line = f"[{x} for x in o]"
                if nullable:
                    line = f"{line} if o is not None else o"
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _compile_list_deserializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> SerializerT:
        # Check for value types
        args = util.get_args(serdes.type)
        arg_deser: Optional[SerializerT] = None
        if args:
            arg_serdes: "Serde" = dataclasses.replace(serdes, type=args[0])
            arg_deser = arg_serdes.serializer
        # Get the important names
        func_name = self._get_name(serdes, tail="deserializer")
        anno_name = f"{func_name}_anno"
        arg_ser_name = f"arg_deser"
        # Build the namespace
        ns = {
            anno_name: serdes.type,
            arg_ser_name: arg_deser,
            "coerce": api.coerce.get_coercer(serdes.type),
        }
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o")) as func:
                # Call the serializer for the value if it exists
                x = f"{arg_ser_name}(x)" if arg_deser else "x"
                # Write the line.
                line = f"coerce(({x} for x in o))"
                if nullable:
                    line = f"{line} if o is not None else o"
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _get_args_serdes(
        self, serdes: "Serde"
    ) -> Tuple[Optional["Serde"], Optional["Serde"]]:
        args = util.get_args(serdes.type)
        kserde, vserde = None, None
        if args:
            # Generate nested serializer if there are arg types.
            kt, vt = args
            kserde, vserde = (
                dataclasses.replace(serdes, type=kt),
                dataclasses.replace(serdes, type=vt),
            )
        return kserde, vserde

    def _compile_dict_serializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> SerializerT:
        config = self._get_configuration(serdes)
        # Check for args
        kser, vser = None, None
        kserde, vserde = self._get_args_serdes(serdes)
        args = all((kserde, vserde))
        if kserde and vserde:
            kser, vser = kserde.serializer, vserde.serializer
        # Get the names for our important variables
        func_name = self._get_name(serdes)
        anno_name = f"{func_name}_anno"
        kser_name = "kser"
        vser_name = "vser"
        # Build the namespace
        ns = {
            anno_name: serdes.type,
            kser_name: kser,
            vser_name: vser,
            "primitive": primitive,
            **config.asdict(),
        }
        ns.update(config.asdict())
        # Build the function
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o")) as func:
                x, y = "primitive(x)", "primitive(y)"
                # If there are args & field mapping, get the correct field name
                # AND serialize the key.
                if args and config.fields_out:
                    x = f"{kser_name}(fields_out.get(x, x))"
                # If there is only a field mapping, get the correct name for the field.
                elif config.fields_out:
                    x = f"fields_out.get(x, x)"
                # If there are only serializers, get the serialized value
                elif args:
                    x = f"{kser_name}(x)"
                    y = f"{vser_name}(y)"
                if config.fields_case:
                    ns.update(case=config.fields_case.transformer)
                    x = f"case({x})"
                # Add a value check if values are provided
                tail = f"if y not in omit_values" if config.omit_values else ""
                # Write the line.
                line = f"{{{x}: {y} for x, y in o.items() {tail}}}"
                if nullable:
                    line = f"{line} if o is not None else o"
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _compile_dict_deserializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> DeserializerT:
        config = self._get_configuration(serdes)
        # Check for args
        kdeser, vdeser = None, None
        kserde, vserde = self._get_args_serdes(serdes)
        args = all((kserde, vserde))
        if kserde and vserde:
            kdeser, vdeser = kserde.deserializer, vserde.deserializer
        # Get the names for our important variables
        func_name = self._get_name(serdes, tail="deserializer")
        anno_name = f"{func_name}_anno"
        kdeser_name = "kdeser"
        vdeser_name = "vdeser"
        coercer_name = "coerce"
        # Build the namespace
        ns = {
            anno_name: serdes.type,
            kdeser_name: kdeser,
            vdeser_name: vdeser,
            coercer_name: api.coerce.get_coercer(serdes.type),
            **config.asdict(),
        }
        # Build the function
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o")) as func:
                x, y = "x", "y"
                # If there are args & field mapping, get the correct field name
                # AND serialize the key.
                if args and config.fields_in:
                    x = f"{kdeser_name}(fields_in.get(x, x))"
                # If there is only a field mapping, get the correct name for the field.
                elif config.fields_in:
                    x = f"fields_in.get(x, x)"
                # If there are only serializers, get the serialized value
                elif args:
                    x = f"{kdeser_name}(x)"
                    y = f"{vdeser_name}(y)"
                # Write the line.
                line = f"{coercer_name}({{{x}: {y} for x, y in o.items()}})"
                if nullable:
                    line = f"{line} if o is not None else o"
                func.l(f"{gen.Keyword.RET} {line}")

        deserializer: DeserializerT = main.compile(name=func_name, ns=ns)
        return deserializer

    def _compile_class_serializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> SerializerT:
        # Get the serializer configuration
        config = self._get_configuration(serdes)
        # Get the important names
        func_name = self._get_name(serdes)
        anno_name = f"{func_name}_anno"
        # Build the function namespace
        ns = {anno_name: serdes.type}
        ns.update(config.asdict())
        # Build the function
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o")) as func:
                # We've mapped the output name with the existing attr name
                x = "fields_out[x]"
                # We have to dynamically call a getter for the value
                y = "fields_ser[x](fields_getters[x](o))"
                # Only add a value filter if we need to, don't waste the cpu time.
                tail = (
                    "if fields_getters[x](o) not in omit_values"
                    if config.omit_values
                    else ""
                )
                line = f"{{{x}: {y} for x in fields_out {tail}}}"
                if nullable:
                    line = f"{line} if o is not None else o"
                # Write the line.
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _compile_class_deserializer(
        self, serdes: "Serde", nullable: bool = False
    ) -> DeserializerT:
        # Get the serializer configuration
        config = self._get_configuration(serdes)
        coercer = api.coerce.get_coercer(serdes.type)
        # Get the important names
        func_name = self._get_name(serdes, tail="deserializer")
        anno_name = f"{func_name}_anno"
        coercer_name = "coerce"
        # Build the function namespace
        ns = {anno_name: serdes.type, coercer_name: coercer, **config.asdict()}
        # Build the function
        with gen.Block(ns) as main:
            with main.f(func_name, gen.Block.p("o"), __eval=util.safe_eval) as func:
                # We've mapped the output name with the existing attr name
                func.l(
                    "_, o = __eval(o) "
                    "if isinstance(o, (str, bytes)) "
                    "else (False, o)"
                )
                line = f"{coercer_name}(o)"
                with func.b("if isinstance(o, Mapping):", Mapping=Mapping) as b:
                    x = "fields_in[x]"
                    y = "fields_deser[x](o[x])" if config.fields_deser else "o[x]"
                    b.l(f"o = {{{x}: {y} for x in fields_in}}")
                if nullable:
                    line = f"{line} if o is not None else o"
                # Write the line.
                func.l(f"{gen.Keyword.RET} {line}")

        deserializer: DeserializerT = main.compile(name=func_name, ns=ns)
        return deserializer

    def _compile_enum_serializer(self, serdes: "Serde") -> SerializerT:
        origin: Type[enum.Enum] = cast(Type[enum.Enum], serdes.origin)
        ts = {*(type(x.value) for x in origin)}
        # If we can predict a single type the return the serializer for that
        if len(ts) == 1:
            t = ts.pop()
            vser = dataclasses.replace(serdes, type=t).serializer

            def serializer(o: enum.Enum):
                return vser(o.value)

            return serializer
        # Else default to lazy serialization
        return primitive

    def _compile_defined_serializer(
        self, serdes: "Serde", ser: SerializerT, nullable: bool = False
    ) -> SerializerT:
        if nullable:
            func_name = self._get_name(serdes)
            ns = {"ser": ser}
            with gen.Block(ns) as main:
                with main.f(func_name, gen.Block.p("o")) as func:
                    func.l(f"{gen.Keyword.RET} ser(o) if o is not None else o")

            serializer: SerializerT = main.compile(name=func_name, ns=ns)
            return serializer
        return ser

    @util.fastcachedmethod
    def _sanity_check_type(self, serdes: "Serde") -> Tuple[bool, "Serde"]:
        should_unwrap = checks.should_unwrap(serdes.type)
        nullable = checks.isoptionaltype(serdes.type)
        if should_unwrap or nullable:
            new = self._extract_arg(serdes.type)
            if new:
                serdes = dataclasses.replace(serdes, type=new)
        return nullable, serdes

    def _compile_serializer(self, serdes: "Serde") -> SerializerT:
        # Check for an optional and extract the type if possible.
        nullable, serdes = self._sanity_check_type(serdes)
        # Lazy shortcut for messy paths (Union, Any, ...)
        if serdes.origin in self._DYNAMIC:
            return primitive
        # Enums are special
        if checks.isenumtype(serdes.type):
            return self._compile_enum_serializer(serdes)
        # Primitives don't require further processing.
        if serdes.origin in self._PRIMITIVES:
            return lambda o: o
        # Defined cases are pre-compiled.
        if serdes.origin in self._DEFINED:
            return self._compile_defined_serializer(
                serdes, self._DEFINED[serdes.origin], nullable=nullable
            )
        # Mapping types need special nested processing as well
        if not checks.istypeddict(serdes.origin) and issubclass(
            serdes.origin, self._DICTITER
        ):
            return self._compile_dict_serializer(serdes, nullable=nullable)
        # Array types need nested processing.
        if not checks.istypedtuple(serdes.origin) and issubclass(
            serdes.origin, self._LISTITER
        ):
            return self._compile_list_serializer(serdes, nullable=nullable)

        return self._compile_class_serializer(serdes, nullable=nullable)

    @util.fastcachedmethod
    def _get_object_fields(self, serdes: "Serde") -> Mapping[str, "Serde"]:
        t = serdes.type
        if checks.iscollectiontype(t) and not (
            checks.istypedtuple(t) or checks.istypeddict(t)
        ):
            return {}
        annos: api.Annotations = {
            x: api.coerce.resolve(y, _constraints=False, _coercer=False)
            for x, y in util.cached_type_hints(t).items()
        }

        return {
            x: dataclasses.replace(serdes, type=util.resolve_supertype(y.un_resolved))
            for x, y in annos.items()
        }

    @util.fastcachedmethod
    def _get_configuration(self, serdes: "Serde") -> SerdeConfig:
        flags: SerdeFlags = serdes.flags
        if hasattr(serdes.origin, _SERDE_FLAGS_ATTR):
            flags = getattr(serdes.origin, _SERDE_FLAGS_ATTR)
            serdes.flags = flags
        # Get all the annotated fields.
        fields = self._get_object_fields(serdes)
        params: Mapping[str, inspect.Parameter]
        try:
            params = (
                util.cached_signature(serdes.type).parameters
                if not issubclass(serdes.origin, Mapping)
                or checks.istypeddict(serdes.origin)
                else {}
            )
        except ValueError:  # pragma: nocover
            params = {}
        # Filter out any annotations which aren't part of the object's signature.
        if flags.signature_only:
            fields = {x: fields[x] for x in fields.keys() & params.keys()}
        # Create a field-to-field mapping
        fields_out = {x: x for x in fields}
        # Make sure to include any fields explicitly listed
        include = flags.fields
        if include:
            if isinstance(include, Mapping):
                fields_out.update(include)
            else:
                fields_out.update({x: x for x in include})
        # Transform the output fields to the correct case.
        if flags.case:
            case = Case(flags.case)
            fields_out = {x: case.transformer(y) for x, y in fields_out.items()}
        omit = flags.omit
        # Omit fields with explicitly omitted types & flag values to omit at dump
        value_omissions: Tuple[Any, ...] = ()
        if omit:
            type_omissions = {o for o in omit if checks._type_check(o)}
            value_omissions = (*(o for o in omit if o not in type_omissions),)
            fields_out = {
                x: y
                for x, y in fields_out.items()
                if fields[x].origin not in type_omissions
            }
        fields_in = {y: x for x, y in fields_out.items()}
        if params:
            fields_in = {x: y for x, y in fields_in.items() if y in params}
        fields_getters = {x: attrgetter(x) for x in fields}
        return SerdeConfig(
            fields_ser={x: y.serializer for x, y in fields.items()},
            fields_deser={x: y.deserializer for x, y in fields.items()},
            fields_out=fields_out,
            fields_in=fields_in,
            fields_getters=fields_getters,
            omit_values=value_omissions,
        )

    def _compile_deserializer(self, serdes: "Serde"):
        nullable, serdes = self._sanity_check_type(serdes)
        if serdes.origin in self._DYNAMIC:
            return lambda o: o
        # Mapping types need special nested processing as well
        coercer = api.coerce.get_coercer(serdes.type, is_optional=nullable)
        shortcuts = {*self._DEFINED, *self._PRIMITIVES}
        if serdes.origin in shortcuts or issubclass(serdes.origin, enum.Enum):
            if nullable:

                def deserializer(o, *, __coerce=coercer):
                    return __coerce(o) if o is not None else o

                return deserializer
            return coercer
        if not checks.istypeddict(serdes.origin) and issubclass(
            serdes.origin, self._DICTITER
        ):
            return self._compile_dict_deserializer(serdes, nullable=nullable)
        # Array types need nested processing.
        if not checks.istypedtuple(serdes.origin) and issubclass(
            serdes.origin, self._LISTITER
        ):
            return self._compile_list_deserializer(serdes, nullable=nullable)

        return self._compile_class_deserializer(serdes, nullable=nullable)

    @util.fastcachedmethod
    def serializer(self, serdes: "Serde"):
        return self._compile_serializer(serdes)

    @util.fastcachedmethod
    def deserializer(self, serdes: "Serde"):
        return self._compile_deserializer(serdes)


_factory = SerdeFactory()


@dataclasses.dataclass(unsafe_hash=True)
class SerdeFlags:
    """Optional settings for a Ser-ialization/de-serialization protocol."""

    signature_only: bool = False
    """Restrict the output of serialization to the class signature."""
    fields: Optional[FieldSettingsT] = None
    """Ensure a set of fields are included in the output.

    If given a mapping, provide a mapping to the output field name.
    """
    case: Optional[Case] = None
    """Select the case-style for the input/output fields."""
    omit: Optional[OmitSettingsT] = None
    """Provide a tuple of types or values which should be omitted on serialization."""

    def __init__(
        self,
        signature_only: bool = False,
        fields: FieldSettingsT = None,
        case: Case = None,
        omit: OmitSettingsT = None,
    ):
        self.signature_only = signature_only
        self.fields = types.FrozenDict._freeze(fields)  # type: ignore
        self.case = case
        self.omit = types.FrozenDict._freeze(omit)  # type: ignore


class AbstractSerde(abc.ABC):
    """An abstract Ser-ialization/de-serialization protocol."""

    @property
    @abc.abstractmethod
    def serializer(self) -> SerializerT:  # pragma: nocover
        ...

    @property
    @abc.abstractmethod
    def deserializer(self) -> DeserializerT:  # pragma: nocover
        ...


@dataclasses.dataclass(unsafe_hash=True)
class Serde(AbstractSerde):
    """Generate a Ser-ialization/de-serialization protocol for a given type.

    See Also
    --------
    :py:class:`SerdeFlags`
    """

    type: Type
    """The target type for the de-/serialization protocol"""
    flags: SerdeFlags = dataclasses.field(default_factory=SerdeFlags)
    """The settings for the  de-/serialization protocol."""

    @property
    def origin(self) -> Type:
        return util.origin(self.type)

    @property
    def factory(self) -> SerdeFactory:
        return _factory

    @util.cached_property
    def serializer(self) -> Callable[[Any], dict]:
        return self.factory.serializer(self)

    @util.cached_property
    def deserializer(self) -> Callable[[Any], Any]:
        return self.factory.deserializer(self)


_SERDE_ATTR = "__serde__"
_SERDE_FLAGS_ATTR = "__serde_flags__"


@functools.singledispatch
def primitive(obj: Any) -> Any:
    """A single-dispatch function for converting an object to its primitive equivalent.

    Useful for encoding data to JSON.

    Registration for custom types may be done by wrapping your handler with
    `@primitive.register`

    Examples
    --------
    >>> import typic
    >>> import datetime
    >>> import uuid
    >>> import ipaddress
    >>> import re
    >>> import dataclasses
    >>> typic.primitive("foo")
    'foo'
    >>> typic.primitive(("foo",))  # containers are converted to lists/dicts
    ['foo']
    >>> typic.primitive(datetime.datetime(1970, 1, 1))  # note that we assume UTC
    '1970-01-01T00:00:00+00:00'
    >>> typic.primitive(b"foo")
    'foo'
    >>> typic.primitive(ipaddress.IPv4Address("0.0.0.0"))
    '0.0.0.0'
    >>> typic.primitive(re.compile("[0-9]"))
    '[0-9]'
    >>> typic.primitive(uuid.UUID(int=0))
    '00000000-0000-0000-0000-000000000000'
    >>> @dataclasses.dataclass
    ... class Foo:
    ...     bar: str = 'bar'
    ...
    >>> typic.primitive(Foo())
    {'bar': 'bar'}
    """
    if hasattr(obj, _SERDE_ATTR):
        return obj.__serde__.serializer(obj)
    if hasattr(obj, "asdict"):  # pragma: nocover
        return {primitive(x): primitive(y) for x, y in obj.asdict().items()}
    if hasattr(obj, "to_dict"):
        return {primitive(x): primitive(y) for x, y in obj.to_dict().items()}
    t = type(obj)
    if checks.isenumtype(t):
        obj = obj.value
        t = type(obj)
    settings = getattr(t, _SERDE_FLAGS_ATTR, SerdeFlags())
    serde = Serde(t, settings)
    return serde.serializer(obj)
