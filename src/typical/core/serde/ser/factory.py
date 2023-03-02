from __future__ import annotations

import dataclasses
import datetime
import decimal
import inspect
import ipaddress
import pathlib
import re
import uuid
from collections import abc
from collections.abc import Collection as Collection_abc
from collections.abc import Iterable as Iterable_abc
from collections.abc import Mapping as Mapping_abc
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Collection,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    TypeVar,
    Union,
    cast,
)

import typical.classes
import typical.inspection
from typical import checks, types
from typical.compat import Literal, Record
from typical.core import constants
from typical.core.interfaces import (
    Annotation,
    DelayedAnnotation,
    ForwardDelayedAnnotation,
    SerdeConfig,
    SerializerT,
)
from typical.core.serde.ser import routines

if TYPE_CHECKING:  # pragma: nocover
    from typical.core.resolver import Resolver


__all__ = ("SerFactory", "SerializationValueError", "DelayedSerializer")


class SerializationValueError(ValueError):
    ...


_T = TypeVar("_T")


class SerFactory:
    """A factory for generating high-performance serializers.

    Notes:
        Should not be used directly.

        Access this functionality via:
          - :py:func:`typical.protocol`
          - :py:func:`typical.primitive`
    """

    def __init__(self, resolver: Resolver):
        self.resolver = resolver
        self._serializer_cache: MutableMapping[str, SerializerT] = {}

    def factory(self, annotation: Annotation[type[_T]]) -> SerializerT[_T]:
        if isinstance(annotation, (DelayedAnnotation, ForwardDelayedAnnotation)):
            return cast(SerializerT, DelayedSerializer(annotation, self))
        annotation.serde = annotation.serde or SerdeConfig()
        return self._compile_serializer(annotation)

    def _compile_serializer(self, annotation: Annotation[type[_T]]) -> SerializerT[_T]:
        # Check for an optional and extract the type if possible.
        func_name = self._get_name(annotation)
        # We've been here before...
        if func_name in self._serializer_cache:
            return self._serializer_cache[func_name]

        serializer: SerializerT[_T]
        routine: routines.BaseSerializerRoutine[_T]
        origin = annotation.resolved_origin
        # Lazy shortcut for messy paths (Union, Any, ...)
        if (
            origin in self._DYNAMIC
            or not annotation.static
            or checks.isuniontype(origin)
        ):
            return cast(SerializerT, self.resolver.primitive)

        if origin in self._DEFINED:
            routine_cls = self._DEFINED[origin]
            serializer = routine_cls(annotation=annotation, resolver=self.resolver)
            self._serializer_cache[func_name] = serializer
            return serializer

        # Routines (functions or methods) can't be serialized...
        if inspect.isroutine(origin) or issubclass(origin, abc.Callable):  # type: ignore
            rname = typical.inspection.get_qualname(origin)

            def _routine_serializer(
                o: Callable, *, name: typical.classes.ReprT = None, lazy: bool = False
            ):
                raise TypeError(f"Routines are not serializeable: {rname!r}")

            routine_serializer = cast("SerializerT[_T]", _routine_serializer)
            self._serializer_cache[func_name] = routine_serializer
            return routine_serializer

        # Enums are special
        if checks.isenumtype(annotation.resolved):
            routine = routines.EnumSerializerRoutine(annotation, self.resolver)
            serializer = cast("SerializerT[_T]", routine)
            self._serializer_cache[func_name] = serializer
            return serializer

        # Primitives don't require further processing.
        # Just check for nullable and the correct type.
        if origin in self._PRIMITIVES:
            routine = routines.NoopSerializerRoutine(annotation, self.resolver)
            serializer = cast("SerializerT[_T]", routine)
            self._serializer_cache[func_name] = serializer
            return serializer

        for t, routine_cls in self._DEFINED.items():
            if issubclass(origin, t):
                serializer = routine_cls(annotation=annotation, resolver=self.resolver)
                self._serializer_cache[func_name] = serializer
                return serializer

        for t in self._PRIMITIVES:
            if issubclass(origin, t):
                routine = routines.CastSerializerRoutine(
                    annotation=annotation, resolver=self.resolver, namespace=t
                )
                serializer = cast("SerializerT[_T]", routine)
                self._serializer_cache[func_name] = serializer
                return serializer

        istypeddict = checks.istypeddict(origin)
        istypedtuple = checks.istypedtuple(origin)
        istypicklass = checks.istypicklass(origin)
        iscollection = issubclass(origin, self._LISTITER)
        ismapping = issubclass(origin, self._DICTITER)

        routine_cls = routines.FieldsSerializerRoutine
        if any((istypeddict, istypedtuple, istypicklass)):
            routine_cls = routines.FieldsSerializerRoutine

        elif (
            issubclass(origin, tuple)
            and annotation.args
            and annotation.args[-1] is not ...
        ):
            routine_cls = routines.FixedTupleSerializerRoutine

        elif ismapping:
            routine_cls = routines.MappingSerializerRoutine
        elif iscollection:
            routine_cls = routines.CollectionSerializerRoutine

        serializer = routine_cls(annotation=annotation, resolver=self.resolver)
        self._serializer_cache[func_name] = serializer
        return serializer

    @staticmethod
    def _get_name(annotation: Annotation) -> str:
        return typical.inspection.get_defname("serializer", annotation)

    _DEFINED: Mapping[type, type[routines.BaseSerializerRoutine]] = {
        ipaddress.IPv4Address: routines.StringSerializerRoutine,
        ipaddress.IPv4Network: routines.StringSerializerRoutine,
        ipaddress.IPv6Address: routines.StringSerializerRoutine,
        ipaddress.IPv6Interface: routines.StringSerializerRoutine,
        ipaddress.IPv6Network: routines.StringSerializerRoutine,
        re.Pattern: routines.PatternSerializerRoutine,
        pathlib.Path: routines.StringSerializerRoutine,
        types.AbsoluteURL: routines.StringSerializerRoutine,
        types.DSN: routines.StringSerializerRoutine,
        types.DirectoryPath: routines.StringSerializerRoutine,
        types.Email: routines.StringSerializerRoutine,
        types.FilePath: routines.StringSerializerRoutine,
        types.HostName: routines.StringSerializerRoutine,
        types.NetworkAddress: routines.StringSerializerRoutine,
        types.RelativeURL: routines.StringSerializerRoutine,
        types.SecretBytes: routines.SecretSerializerRoutine,
        types.SecretStr: routines.SecretSerializerRoutine,
        types.URL: routines.StringSerializerRoutine,
        uuid.UUID: routines.StringSerializerRoutine,
        decimal.Decimal: routines.StringSerializerRoutine,
        bytes: routines.BytesSerializerRoutine,
        bytearray: routines.BytesSerializerRoutine,
        datetime.date: routines.ISOFormatSerializerRoutine,
        datetime.datetime: routines.ISOFormatSerializerRoutine,
        datetime.time: routines.ISOFormatSerializerRoutine,
        datetime.timedelta: routines.ISOFormatSerializerRoutine,
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
    _DICTITER = (dict, Mapping, Mapping_abc, MappingProxyType, types.FrozenDict, Record)
    _PRIMITIVES = (str, int, bool, float, type(None), type(...))
    _DYNAMIC: frozenset[Any] = frozenset(
        {
            Union,
            Any,
            inspect.Parameter.empty,
            dataclasses.MISSING,
            ClassVar,
            Literal,
            constants.empty,
        }
    )
    _FNAME = "fname"


class DelayedSerializer:
    __slots__ = "anno", "factory", "_serializer", "__name__"

    def __init__(
        self,
        anno: Union[DelayedAnnotation, ForwardDelayedAnnotation],
        factory: SerFactory,
    ):
        self.anno = anno
        self.factory = factory
        self._serializer: Optional[SerializerT] = None
        self.__name__ = anno.name

    def __call__(self, *args, **kwargs):
        if self._serializer is None:
            self._serializer = self.factory.factory(self.anno.resolved.annotation)
        return self._serializer(*args, **kwargs)
