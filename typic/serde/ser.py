from __future__ import annotations

import dataclasses
import datetime
import decimal
import enum
import inspect
import ipaddress
import pathlib
import re
import uuid
from collections import abc
from collections.abc import (
    Mapping as Mapping_abc,
    Collection as Collection_abc,
    Iterable as Iterable_abc,
)
from operator import methodcaller, attrgetter
from types import MappingProxyType
from typing import (
    Type,
    Callable,
    Collection,
    Union,
    Mapping,
    Any,
    ClassVar,
    cast,
    TYPE_CHECKING,
    Iterable,
    MutableMapping,
    Dict,
    Optional,
    TypeVar,
)

from typic import util, checks, gen, types
from typic.common import DEFAULT_ENCODING
from typic.compat import Literal
from .common import (
    SerializerT,
    SerdeConfig,
    Annotation,
    ForwardDelayedAnnotation,
    DelayedAnnotation,
)

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver


class SerializationValueError(ValueError):
    ...


_decode = methodcaller("decode", DEFAULT_ENCODING)
_pattern = attrgetter("pattern")
_T = TypeVar("_T")


class SerFactory:
    """A factory for generating high-performance serializers.
    Notes
    -----
    Should not be used directly.
    """

    _DEFINED: Mapping[Type, SerializerT] = {
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
        types.SecretBytes: cast(SerializerT, lambda o: _decode(o.secret)),
        types.SecretStr: cast(SerializerT, attrgetter("secret")),
        types.URL: str,
        uuid.UUID: str,
        decimal.Decimal: float,
        bytes: cast(SerializerT, _decode),
        bytearray: cast(SerializerT, _decode),
        datetime.date: cast(SerializerT, util.isoformat),
        datetime.datetime: cast(SerializerT, util.isoformat),
        datetime.time: cast(SerializerT, util.isoformat),
        datetime.timedelta: cast(SerializerT, util.isoformat),
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
    _PRIMITIVES = (str, int, bool, float, type(None), type(...))
    _DYNAMIC = frozenset(
        {Union, Any, inspect.Parameter.empty, dataclasses.MISSING, ClassVar, Literal}
    )
    _FNAME = "fname"

    def __init__(self, resolver: Resolver):
        self.resolver = resolver
        self._serializer_cache: MutableMapping[str, SerializerT] = {}

    @staticmethod
    def _get_name(annotation: Annotation) -> str:
        return util.get_defname("serializer", annotation)

    def _check_add_null_check(self, func: gen.Function, annotation: Annotation):
        if annotation.optional:
            with func.b(f"if o in {self.resolver.OPTIONALS}:") as b:
                b.l(f"{gen.Keyword.RET}")

    def _add_type_check(self, func: gen.Function, annotation: Annotation):
        resolved_name = util.get_name(annotation.resolved)
        func.l(f"{self._FNAME} = name or {resolved_name!r}")
        line = "if not tcheck(o.__class__, t):"
        check: Callable[..., bool] = util.cached_issubclass
        t = annotation.generic
        if checks.isbuiltinsubtype(annotation.generic):
            line = "if not tcheck(o, t):"
            check = isinstance  # type: ignore
        if checks.istypeddict(t):
            t = dict
        with func.b(line, tcheck=check) as b:
            msg = (
                f"{{{self._FNAME}}}: type {{inst_tname!r}} "
                f"is not a subtype of type "
                f"{util.get_qualname(annotation.generic)!r}. "
                f"Perhaps this annotation should be "
                f"Union[{{inst_tname}}, {util.get_qualname(annotation.generic)}]?"
            )
            b.l("inst_tname = qualname(o.__class__)")
            b.l(
                f"raise err(f{msg!r})",
                err=SerializationValueError,
                qualname=util.get_qualname,
                t=t,
            )

    def _build_list_serializer(
        self,
        func: gen.Function,
        annotation: Annotation,
    ):
        # Check for value types
        ns: Dict[str, Any] = {}
        self._check_add_null_check(func, annotation)
        self._add_type_check(func, annotation)
        arg_ser: SerializerT = cast(SerializerT, self.resolver.primitive)
        if annotation.args:
            arg_a: Annotation = self.resolver.annotation(
                annotation.args[0], flags=annotation.serde.flags
            )
            arg_ser = self.factory(arg_a)

        arg_ser_name = "arg_ser"
        ns[arg_ser_name] = arg_ser
        func.l(f"gen = ({arg_ser_name}(v) for v in o)")
        line = "gen if lazy else [*gen]"
        func.l(f"{gen.Keyword.RET} {line}", level=None, **ns)

    def _build_dict_serializer(self, func: gen.Function, annotation: Annotation):
        # Check for args
        kser_: SerializerT
        vser_: SerializerT
        kser_, vser_ = cast(SerializerT, self.resolver.primitive), cast(
            SerializerT, self.resolver.primitive
        )
        args = util.get_args(annotation.resolved)
        if args:
            kt, vt = args
            ktr: Annotation = self.resolver.annotation(kt, flags=annotation.serde.flags)
            vtr: Annotation = self.resolver.annotation(vt, flags=annotation.serde.flags)
            kser_, vser_ = (self.factory(ktr), self.factory(vtr))
        # Add sanity checks.
        self._check_add_null_check(func, annotation)
        self._add_type_check(func, annotation)
        ns: Dict[str, Any] = {
            "kser": kser_,
            "vser": vser_,
        }
        ksercall = "kser(k)"
        if annotation.serde.fields_out:
            ns["fields_out"] = annotation.serde.fields_out
            ksercall = "kser(fields_out.get(k, k))"
        if annotation.serde.flags.case:
            ns["case"] = annotation.serde.flags.case.transformer
            ksercall = f"case({ksercall})"
        gencall = f"({ksercall}, vser(v)) for k, v in o.items()"
        if annotation.serde.flags.omit:
            ns["omit"] = annotation.serde.flags.omit
            gencall = f"{gencall} if v not in omit"
        func.l(
            f"gen = ({gencall})",
            **ns,
        )
        func.l(f"{gen.Keyword.RET} gen if lazy else {{k: v for k, v in gen}}")

    def _build_class_serializer(
        self,
        func: gen.Function,
        annotation: Annotation,
    ):
        # Get the field serializers
        fields_ser = {x: self.factory(y) for x, y in annotation.serde.fields.items()}
        iterator = self.resolver.translator.iterator(
            annotation.resolved,
            relaxed=True,
            # We want to proactively exclude defined fields from this iterator.
            exclude=(*annotation.serde.flags.exclude,),
        )
        self._check_add_null_check(func, annotation)
        self._add_type_check(func, annotation)
        ns: Dict[str, Any] = {
            "fields_ser": fields_ser,
            "fields_out": annotation.serde.fields_out.keys(),
            "iterator": iterator,
        }
        # Determine how to dump the field.
        f = "f"
        # Get the mapping of attr->out
        # If we have transforms, make sure we use them on dump.
        transforms = {f: t for f, t in annotation.serde.fields_out.items() if f != t}
        if transforms:
            ns["transforms"] = transforms
            f = "transforms.get(f, f)"
        # Define the generator expression.
        gencall = f"({f}, fields_ser[f](v)) for f, v in iterator(o) if f in fields_out"
        if annotation.serde.flags.omit:
            ns["omit"] = annotation.serde.flags.omit
            gencall = f"{gencall} and v not in omit"

        func.l(f"gen = ({gencall})", **ns)
        func.l(f"{gen.Keyword.RET} gen if lazy else {{f: v for f, v in gen}}")

    def _compile_enum_serializer(self, annotation: Annotation) -> SerializerT:
        origin: Type[enum.Enum] = cast(Type[enum.Enum], annotation.resolved_origin)
        ts = {type(x.value) for x in origin}
        # If we can predict a single type the return the serializer for that
        if len(ts) == 1:
            t = ts.pop()
            va = self.resolver.annotation(t, flags=annotation.serde.flags)
            vser = self.factory(va)

            def serializer(
                o: enum.Enum, *, lazy: bool = False, name: util.ReprT = None, _vser=vser
            ):
                return _vser(o.value, lazy=lazy, name=name)

            return cast(SerializerT, serializer)
        # Else default to lazy serialization
        return cast(SerializerT, self.resolver.primitive)

    def _compile_defined_serializer(
        self,
        annotation: Annotation[Type[_T]],
        ser: SerializerT[_T],
    ) -> SerializerT[_T]:
        func_name = self._get_name(annotation)
        ser_name = "ser"
        ns = {ser_name: ser}
        with gen.Block(ns) as main:
            with self._define(main, func_name) as func:
                self._check_add_null_check(func, annotation)
                self._add_type_check(func, annotation)
                line = f"{ser_name}(o)"
                if annotation.origin in (type(o) for o in self.resolver.OPTIONALS):
                    line = "None"
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

    def _compile_defined_subclass_serializer(
        self, origin: Type, annotation: Annotation
    ):
        for t, s in self._DEFINED.items():
            if issubclass(origin, t):
                return self._compile_defined_serializer(annotation, s)
        # pragma: nocover

    def _compile_primitive_subclass_serializer(
        self, origin: Type, annotation: Annotation
    ):
        for t in self._PRIMITIVES:
            if issubclass(origin, t):
                return self._compile_defined_serializer(annotation, t)
        # pragma: nocover

    def _compile_serializer(self, annotation: Annotation[Type[_T]]) -> SerializerT[_T]:
        # Check for an optional and extract the type if possible.
        func_name = self._get_name(annotation)
        # We've been here before...
        if func_name in self._serializer_cache:
            return self._serializer_cache[func_name]

        serializer: SerializerT
        origin = annotation.resolved_origin
        # Lazy shortcut for messy paths (Union, Any, ...)
        if (
            origin in self._DYNAMIC
            or not annotation.static
            or checks.isuniontype(origin)
        ):
            serializer = cast(SerializerT, self.resolver.primitive)
        # Routines (functions or methods) can't be serialized...
        elif issubclass(origin, abc.Callable) or inspect.isroutine(origin):  # type: ignore
            name = util.get_qualname(origin)
            with gen.Block() as main:
                with self._define(main, func_name) as func:
                    func.l(
                        f'raise TypeError("Routines are not serializable. ({name!r}).")'
                    )

            serializer = main.compile(name=func_name)
            self._serializer_cache[func_name] = serializer
        # Enums are special
        elif checks.isenumtype(annotation.resolved):
            serializer = self._compile_enum_serializer(annotation)
        # Primitives don't require further processing.
        # Just check for nullable and the correct type.
        elif origin in self._PRIMITIVES:
            ns: dict = {}
            with gen.Block(ns) as main:
                with self._define(main, func_name) as func:
                    self._check_add_null_check(func, annotation)
                    self._add_type_check(func, annotation)
                    line = "o"
                    if annotation.origin in (type(o) for o in self.resolver.OPTIONALS):
                        line = "None"
                    func.l(f"{gen.Keyword.RET} {line}")

            serializer = main.compile(name=func_name, ns=ns)
            self._serializer_cache[func_name] = serializer

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
            with gen.Block(ns) as main:
                with self._define(main, func_name) as func:
                    # Mapping types need special nested processing as well
                    istypeddict = checks.istypeddict(origin)
                    istypedtuple = checks.istypedtuple(origin)
                    istypicklass = checks.istypicklass(origin)
                    if not istypeddict and issubclass(origin, self._DICTITER):
                        self._build_dict_serializer(func, annotation)
                    # Array types need nested processing.
                    elif (
                        not istypedtuple
                        and not istypeddict
                        and not istypicklass
                        and issubclass(origin, self._LISTITER)
                    ):
                        self._build_list_serializer(func, annotation)
                    # Build a serializer for a structured class.
                    else:
                        self._build_class_serializer(func, annotation)
            serializer = main.compile(name=func_name, ns=ns)
            self._serializer_cache[func_name] = serializer
        return serializer

    @staticmethod
    def _define(main: gen.Block, name: str) -> gen.Function:
        return main.func(
            name,
            main.param("o"),
            main.param("lazy", default=False, kind=gen.ParameterKind.KEYWORD_ONLY),
            main.param("name", default=None, kind=gen.ParameterKind.KEYWORD_ONLY),
        )

    def factory(self, annotation: Annotation[Type[_T]]) -> SerializerT[_T]:
        if isinstance(annotation, (DelayedAnnotation, ForwardDelayedAnnotation)):
            return cast(SerializerT, DelayedSerializer(annotation, self))
        annotation.serde = annotation.serde or SerdeConfig()
        return self._compile_serializer(annotation)


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
