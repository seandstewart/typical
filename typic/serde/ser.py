import dataclasses
import datetime
import decimal
import enum
import inspect
import ipaddress
import pathlib
import re
import uuid
from collections.abc import (
    Mapping as Mapping_abc,
    Collection as Collection_abc,
    Iterable as Iterable_abc,
)
from operator import attrgetter, methodcaller
from types import MappingProxyType
from typing import (
    Type,
    Optional,
    Callable,
    Collection,
    Union,
    Mapping,
    Any,
    ClassVar,
    cast,
    TYPE_CHECKING,
    TypeVar,
    Iterable,
    MutableMapping,
)

from typic import util, checks, gen, types
from typic.common import DEFAULT_ENCODING
from .common import SerializerT, SerdeConfig, Annotation

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver


def _iso(o) -> str:
    if isinstance(o, (datetime.datetime, datetime.time)) and not o.tzinfo:
        return f"{o.isoformat()}+00:00"
    return o.isoformat()


_decode = methodcaller("decode", DEFAULT_ENCODING)
_total_secs = methodcaller("total_seconds")
_pattern = attrgetter("pattern")

_T = TypeVar("_T")


class SerFactory:
    """A factory for generating high-performance serializers.

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

    _LISTITER = (
        list,
        tuple,
        set,
        frozenset,
        Collection,
        Collection_abc,
        Iterable,
        Iterable_abc,
    )
    _DICTITER = (dict, Mapping, Mapping_abc, MappingProxyType, types.FrozenDict)
    _PRIMITIVES = (str, int, bool, float, type(None))
    _DYNAMIC = frozenset(
        {Union, Any, inspect.Parameter.empty, dataclasses.MISSING, ClassVar}
    )

    def __init__(self, resolver: "Resolver"):
        self.resolver = resolver
        self._serializer_cache: MutableMapping[str, SerializerT] = {}

    @staticmethod
    def _get_name(annotation: "Annotation") -> str:
        return f"serializer_{util.hexhash(annotation)}"

    def _build_list_serializer(
        self, func: gen.Block, annotation: "Annotation",
    ):
        # Check for value types
        arg_ser: Optional[SerializerT] = None
        if annotation.args:
            arg_a: "Annotation" = self.resolver.annotation(
                annotation.args[0], flags=annotation.serde.flags
            )
            arg_ser = self.factory(arg_a)
        # Get the important names
        arg_ser_name = f"arg_ser"
        # Build the namespace
        ns = {arg_ser_name: arg_ser}
        # Call the serializer for the value if it exists
        x = f"{arg_ser_name}(x)" if arg_ser else "x"
        # Write the line.
        line = f"[{x} for x in o]"
        if annotation.optional:
            line = f"{line} if o is not None else o"
        func.l(f"{gen.Keyword.RET} {line}", level=None, **ns)

    def _build_dict_serializer(self, func: gen.Block, annotation: "Annotation"):
        # Check for args
        kser, vser = None, None
        args = util.get_args(annotation.resolved)
        if args:
            kt, vt = args
            ktr: "Annotation" = self.resolver.annotation(
                kt, flags=annotation.serde.flags
            )
            vtr: "Annotation" = self.resolver.annotation(
                vt, flags=annotation.serde.flags
            )
            kser, vser = (self.factory(ktr), self.factory(vtr))
        # Get the names for our important variables
        kser_name = "kser"
        vser_name = "vser"
        # Build the namespace
        ns = {
            kser_name: kser,
            vser_name: vser,
            "primitive": self.resolver.primitive,
        }
        # Build the function
        x, y = "primitive(x)", "primitive(y)"
        # If there are args & field mapping, get the correct field name
        # AND serialize the key.
        if args and annotation.serde.fields_out:
            x = f"{kser_name}(fields_out.get(x, x))"
        # If there is only a field mapping, get the correct name for the field.
        elif annotation.serde.fields_out:
            x = f"fields_out.get(x, x)"
        # If there are only serializers, get the serialized value
        elif args:
            x = f"{kser_name}(x)"
            y = f"{vser_name}(y)"
        if annotation.serde.flags.case:
            ns.update(case=annotation.serde.flags.case.transformer)
            x = f"case({x})"
        # Add a value check if values are provided
        tail = f"if y not in omit_values" if annotation.serde.omit_values else ""
        # Write the line.
        line = f"{{{x}: {y} for x, y in o.items() {tail}}}"
        if annotation.optional:
            line = f"{line} if o is not None else o"
        func.l(f"{gen.Keyword.RET} {line}", **ns)

    def _build_class_serializer(
        self, func: gen.Block, annotation: "Annotation",
    ):
        # We've mapped the output name with the existing attr name
        x = "fields_out[x]"
        # We have to dynamically call a getter for the value
        y = "fields_ser[x](fields_getters[x](o))"
        # Only add a value filter if we need to, don't waste the cpu time.
        tail = (
            "if fields_getters[x](o) not in omit_values"
            if annotation.serde.omit_values
            else ""
        )
        line = f"{{{x}: {y} for x in fields_out {tail}}}"
        if annotation.optional:
            line = f"{line} if o is not None else o"
        # Get the field serializers
        fields_ser = {x: self.factory(y) for x, y in annotation.serde.fields.items()}
        # Write the line.
        func.l(f"{gen.Keyword.RET} {line}", fields_ser=fields_ser)

    def _compile_enum_serializer(self, annotation: "Annotation",) -> SerializerT:
        origin: Type[enum.Enum] = cast(
            Type[enum.Enum], util.origin(annotation.resolved)
        )
        ts = {type(x.value) for x in origin}
        # If we can predict a single type the return the serializer for that
        if len(ts) == 1:
            t = ts.pop()
            va = self.resolver.annotation(t, flags=annotation.serde.flags)
            vser = self.factory(va)

            def serializer(o: enum.Enum):
                return vser(o.value)

            return serializer
        # Else default to lazy serialization
        return self.resolver.primitive

    def _compile_defined_serializer(
        self, annotation: "Annotation", ser: SerializerT,
    ) -> SerializerT:
        if annotation.optional:
            func_name = self._get_name(annotation)
            ns = {"ser": ser}
            with gen.Block(ns) as main:
                with main.f(func_name, gen.Block.p("o")) as func:
                    func.l(f"{gen.Keyword.RET} ser(o) if o is not None else o")

            serializer: SerializerT = main.compile(name=func_name, ns=ns)
            return serializer
        return ser

    def _compile_defined_subclass_serializer(
        self, origin: Type, annotation: "Annotation"
    ):
        for t, s in self._DEFINED.items():
            if issubclass(origin, t):
                return self._compile_defined_serializer(annotation, s)
        # pragma: nocover

    def _compile_primitive_subclass_serializer(
        self, origin: Type, annotation: "Annotation"
    ):
        for t in self._PRIMITIVES:
            if issubclass(origin, t):
                return self._compile_defined_serializer(annotation, t)
        # pragma: nocover

    def _compile_serializer(self, annotation: "Annotation") -> SerializerT:
        # Check for an optional and extract the type if possible.
        func_name = self._get_name(annotation)
        # We've been here before...
        if func_name in self._serializer_cache:
            return self._serializer_cache[func_name]

        serializer: SerializerT
        origin = util.origin(annotation.resolved)
        # Lazy shortcut for messy paths (Union, Any, ...)
        if origin in self._DYNAMIC or not annotation.static:
            serializer = self.resolver.primitive
        # Enums are special
        elif checks.isenumtype(annotation.resolved):
            serializer = self._compile_enum_serializer(annotation)
        # Primitives don't require further processing.
        elif origin in self._PRIMITIVES:

            def serializer(o: _T) -> _T:
                return o

        # Defined cases are pre-compiled, but we have to check for optionals.
        elif origin in self._DEFINED:
            serializer = self._compile_defined_serializer(
                annotation, self._DEFINED[origin]
            )
        elif issubclass(origin, (*self._DEFINED,)):
            serializer = self._compile_defined_subclass_serializer(origin, annotation)
        elif issubclass(origin, self._PRIMITIVES):
            serializer = self._compile_primitive_subclass_serializer(origin, annotation)
        else:
            # Build the function namespace
            anno_name = f"{func_name}_anno"
            ns = {anno_name: origin, **annotation.serde.asdict()}
            try:
                # Optimization: try to make the values to omit a set for O(1) lookups.
                ns["omit_values"] = {*ns["omit_values"]}
            except TypeError:  # pragma: nocover
                # Oh well - it'll have to be expensive.
                pass
            with gen.Block(ns) as main:
                with main.f(func_name, gen.Block.p("o")) as func:
                    # Mapping types need special nested processing as well
                    if not checks.istypeddict(origin) and issubclass(
                        origin, self._DICTITER
                    ):
                        self._build_dict_serializer(func, annotation)
                    # Array types need nested processing.
                    elif not checks.istypedtuple(origin) and issubclass(
                        origin, self._LISTITER
                    ):
                        self._build_list_serializer(func, annotation)
                    # Build a serializer for a structured class.
                    else:
                        self._build_class_serializer(func, annotation)
            serializer = main.compile(name=func_name, ns=ns)
            self._serializer_cache[func_name] = serializer
        return serializer

    def factory(self, annotation: "Annotation"):
        annotation.serde = annotation.serde or SerdeConfig()
        return self._compile_serializer(annotation)
