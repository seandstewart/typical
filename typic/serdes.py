import dataclasses
import datetime
import enum
import ipaddress
import pathlib
import re
import uuid
from collections.abc import Mapping as Mapping_abc, Collection as Collection_abc
from functools import partial
from operator import attrgetter, itemgetter
from typing import (
    Type,
    Optional,
    Callable,
    Collection,
    Union,
    Tuple,
    Mapping,
    Any,
    cast,
)

import inflection

from typic import util, checks, api, gen


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


AnyOrTypeT = Union[Type, Any]
FieldSettingsT = Union[Tuple[str, ...], Mapping[str, str]]
"""Specify the fields to include. 

Optionally map to an alternative name for output.
"""
OmitSettingsT = Tuple[AnyOrTypeT, ...]
"""Specify types or values which you wish to omit from the output."""
SerializerT = Callable[[Any], api.ObjectT]
"""The signature of a type serializer."""


def _decode(o) -> str:
    return o.decode(util.DEFAULT_ENCODING)


def _iso(o) -> str:
    if isinstance(o, (datetime.datetime, datetime.time)) and not o.tzinfo:
        return f"{o.isoformat()}+00:00"
    return o.isoformat()


@dataclasses.dataclass
class SerdesConfig:
    fields: api.Annotations = dataclasses.field(default_factory=dict)
    fields_out: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_in: Mapping[str, str] = dataclasses.field(default_factory=dict)
    fields_getters: Mapping[str, Callable[[str], Any]] = dataclasses.field(
        default_factory=dict
    )
    omit_values: Tuple[Any, ...] = dataclasses.field(default_factory=tuple)


class SerDesFactory:

    _DEFINED: Mapping[Type, Callable[[Any], Any]] = {
        ipaddress.IPv4Address: str,
        ipaddress.IPv4Network: str,
        ipaddress.IPv6Address: str,
        ipaddress.IPv6Interface: str,
        ipaddress.IPv6Network: str,
        pathlib.Path: str,
        uuid.UUID: str,
        bytes: _decode,
        bytearray: _decode,
        datetime.date: _iso,
        datetime.datetime: _iso,
        datetime.time: _iso,
    }

    _LISTITER = frozenset({list, tuple, set, frozenset, Collection, Collection_abc,})
    _DICTITER = frozenset({dict, Mapping, Mapping_abc})
    _PRIMITIVES = frozenset({str, int, bool, float, type(None)})

    def _get_name(self, serdes: "SerDes") -> str:
        return re.sub(r"\W+", "_", f"{serdes.type}_serializer")

    def _compile_list_serializer(self, serdes: "SerDes") -> SerializerT:
        args = util.get_args(serdes.type)
        arg_ser: Optional[SerializerT] = None
        if args:
            arg_serdes: "SerDes" = dataclasses.replace(serdes, type=args[0])
            arg_ser = arg_serdes.serializer
        func_name = self._get_name(serdes)
        anno_name = f"{func_name}_anno"
        arg_ser_name = f"{func_name}_arg_ser"
        ns = {anno_name: serdes.type, arg_ser_name: arg_ser}
        with gen.Block(ns) as main:
            with main.f(func_name, main.p("o")) as func:
                x = f"{arg_ser_name}(x)" if arg_ser else "x"
                func.l(f"{gen.Keyword.RET} [{x} for x in o]")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _compile_dict_args_serializer(
        self,
        serdes: "SerDes",
        args: Tuple[Type, Type],
        fout: Mapping[str, str],
        ov: Tuple[Any, ...],
    ) -> SerializerT:
        kt, vt = args
        kser, vser = (
            dataclasses.replace(serdes, type=kt).serializer,
            dataclasses.replace(serdes, type=vt).serializer,
        )

        def serializer(o: Mapping) -> dict:
            return {kser(x): vser(y) for x, y in o.items()}

        if fout and ov:

            def serializer(o: Mapping) -> dict:
                return {
                    kser(fout.get(x, x)): vser(y) for x, y in o.items() if y not in ov
                }

        elif fout:

            def serializer(o: Mapping) -> dict:
                return {kser(fout.get(x, x)): vser(y) for x, y in o.items()}

        elif ov:

            def serializer(o: Mapping) -> dict:
                return {kser(x): vser(y) for x, y in o.items() if y not in ov}

        return serializer

    def _compile_dict_serializer(self, serdes: "SerDes") -> SerializerT:
        def serializer(o: Mapping) -> dict:
            return {x: y for x, y in o.items()}

        args = util.get_args(serdes.type)
        config = self._get_configuration(serdes)
        fout, ov = (
            config.fields_out,
            config.omit_values,
        )
        if args:
            serializer = self._compile_dict_args_serializer(
                serdes=serdes, args=args, fout=fout, ov=ov
            )

        elif fout:

            def serializer(o: Mapping) -> dict:
                return {fout.get(x, x): y for x, y in o.items()}

            if ov:

                def serializer(o: Mapping) -> dict:
                    return {fout.get(x, x): y for x, y in o.items() if y not in ov}

        elif ov:

            def serializer(o: Mapping) -> dict:
                return {x: y for x, y in o.items() if y not in ov}

        return serializer

    def _compile_serializer(self, serdes: "SerDes") -> SerializerT:
        if serdes.origin in self._PRIMITIVES:
            return lambda o: o
        if serdes.origin in self._DEFINED:
            return self._DEFINED[serdes.type]
        if serdes.origin in self._LISTITER:
            return self._compile_list_serializer(serdes)
        if serdes.origin in self._DICTITER:
            return self._compile_dict_serializer(serdes)

        config = self._get_configuration(serdes)
        fout, fget, f, ov = (
            config.fields_out,
            config.fields_getters,
            config.fields,
            config.omit_values,
        )
        if ov:

            def serializer(o: Any) -> dict:
                return {fout[x]: f[x](fget[x](o)) for x in fout if fget[x](o) not in ov}

        else:

            def serializer(o: Any) -> dict:
                return {fout[x]: f[x](fget[x](o)) for x in fout if fget[x](o)}

        return serializer

    @util.fastcachedmethod
    def _get_object_fields(self, serdes: "SerDes") -> Mapping[str, "SerDes"]:
        t = serdes.type
        if checks.iscollectiontype(t) and not (
            checks.istypedtuple(t) or checks.istypeddict(t)
        ):
            return {}
        annos: api.Annotations = api.annotations(t)

        return {
            x: dataclasses.replace(serdes, type=y.annotation).serializer
            for x, y in annos.items()
        }

    @util.fastcachedmethod
    def _get_configuration(self, serdes: "SerDes") -> SerdesConfig:
        # Get all the annotated fields.
        fields = self._get_object_fields(serdes)
        # Filter out any annotations which aren't part of the object's signature.
        if serdes.settings.signature_only:
            params = util.cached_signature(serdes.type).parameters
            fields = {x: fields[x] for x in fields.keys() & params.keys()}
        # Create a field-to-field mapping
        fields_out = {x: x for x in fields}
        # Make sure to include any fields explicitly listed
        include = serdes.settings.fields
        if include:
            if isinstance(include, Mapping):
                fields_out.update(include)
            else:
                fields_out.update({x: x for x in include})
        # Transform the output fields to the correct case.
        if serdes.settings.case:
            case = Case(serdes.settings.case)
            fields_out = {x: case.transformer(y) for x, y in fields_out.items()}
        omit = serdes.settings.omit
        # Omit fields with explicitly omitted types & flag values to omit
        value_omissions: Tuple[Any, ...] = ()
        if omit:
            type_omissions = {o for o in omit if checks._type_check(o)}
            value_omissions = (*(o for o in omit if o not in type_omissions),)
            fields_out = {
                x: y
                for x, y in fields_out.items()
                if fields[x].origin in type_omissions
            }
        fields_in = {y: x for x, y in fields_out.items()}
        return SerdesConfig(
            fields=fields,
            fields_out=fields_out,
            fields_in=fields_in,
            omit_values=value_omissions,
        )

    def _compile_deserializer(self, serdes: "SerDes"):
        coercer = api.coerce.get_coercer(serdes.type)
        config = self._get_configuration(serdes)
        fin = config.fields_in

        def deserializer(o: Any):
            _, o = util.safe_eval(o) if isinstance(o, (str, bytes)) else (False, o)
            o = {fin[x]: y for x, y in o.items()} if isinstance(o, Mapping) else o

            return coercer(o)

        return deserializer

    @util.fastcachedmethod
    def serializer(self, serdes: "SerDes"):
        return self._compile_serializer(serdes)

    @util.fastcachedmethod
    def deserializer(self, serdes: "SerDes"):
        return self._compile_deserializer(serdes)


_factory = SerDesFactory()


@dataclasses.dataclass(frozen=True)
class SerDesSettings:
    signature_only: bool = False
    fields: Optional[FieldSettingsT] = None
    case: Optional[Case] = None
    omit: Optional[OmitSettingsT] = None


@dataclasses.dataclass(frozen=True)
class SerDes:
    type: Type
    settings: SerDesSettings = dataclasses.field(default_factory=SerDesSettings)

    @property
    def origin(self) -> Type:
        return util.origin(self.type)

    @util.cached_property
    def factory(self) -> SerDesFactory:
        return _factory

    @util.cached_property
    def serializer(self) -> Callable[[Any], dict]:
        return self.factory.serializer(self)

    @util.cached_property
    def deserializer(self) -> Callable[[Any], Any]:
        return self.factory.deserializer(self)
