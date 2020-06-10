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
    TypeVar,
    Iterable,
    MutableMapping,
    ItemsView,
    KeysView,
    ValuesView,
    Dict,
)

from typic import util, checks, gen, types
from typic.ext import json
from typic.common import DEFAULT_ENCODING
from .common import (
    SerializerT,
    SerdeConfig,
    Annotation,
    Unprocessed,
    Omit,
    KT,
    VT,
)


if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver


_T = TypeVar("_T")


def make_class_serdict(annotation: "Annotation", fields: Mapping[str, SerializerT]):
    name = f"{util.get_name(annotation.resolved_origin)}SerDict"
    bases = (ClassFieldSerDict,)
    getters = annotation.serde.fields_getters
    omit = (*annotation.serde.omit_values,)
    if annotation.serde.fields_out:
        fout = annotation.serde.fields_out
        getters = {y: getters[x] for x, y in fout.items()}
        fields = {y: fields[x] for x, y in fout.items()}

    def getitem(self, key):
        v = dict.__getitem__(self, key)
        return self.__missing__(key) if v is Unprocessed else v

    if omit:

        def missing(
            self,
            item,
            *,
            __fields=fields,
            __getters=getters,
            __repr=util.joinedrepr,
            __omit=omit,
        ):
            raw = __getters[item](self.instance)
            if raw not in __omit:
                self[item] = ret = __fields[item](
                    raw, lazy=self.lazy, name=__repr(self._name, item)
                )
                return ret
            return Omit

        def iter(self, *, __fields=fields.keys(), Omit=Omit):
            for k in fields:
                v = self.__missing__(k)
                if v is Omit:
                    continue
                yield k

    else:

        def missing(  # type: ignore
            self, item, *, __fields=fields, __getters=getters, __repr=util.joinedrepr,
        ):
            self[item] = ret = __fields[item](
                __getters[item](self.instance),
                lazy=self.lazy,
                name=__repr(self._name, item),
            )
            return ret

        def iter(self, *, __fields=fields.keys()):  # type: ignore
            for k in __fields:
                self.__missing__(k)
                yield k

    stdlib = json.using_stdlib()
    ns = dict(
        lazy=False,
        getters=getters,
        fields=fields,
        omit=(*annotation.serde.omit_values,),
        type=annotation.resolved_origin,
        __missing__=missing,
        __iter__=iter,
        stdlib=stdlib,
    )
    if stdlib:
        ns["__getitem__"] = getitem
    return type(name, bases, ns)


class SerializationValueError(ValueError):
    ...


class ClassFieldSerDict(dict):
    type: Type
    instance: Any
    lazy: bool
    getters: Mapping[str, Callable[[str], Any]]
    fields: Mapping[str, SerializerT]
    omit: Iterable[Any]
    stdlib: bool

    __slots__ = ("instance", "lazy", "_name")

    def __init__(
        self, instance: Any, lazy: bool = False, *, __tfname__: util.ReprT = None,
    ):
        self._name = __tfname__
        self.instance = instance
        self.lazy = lazy
        if self.stdlib:
            dict.__init__(self, dict.fromkeys(self.fields, Unprocessed))

    def __hash__(self):
        return self.instance.__hash__()

    def items(self) -> ItemsView[KT, VT]:  # pragma: nocover
        return ItemsView(self)  # type: ignore

    def keys(self) -> KeysView[KT]:  # pragma: nocover
        return KeysView(self)  # type: ignore

    def values(self) -> ValuesView[VT]:  # pragma: nocover
        return ValuesView(self)  # type: ignore


def make_kv_serdict(annotation: "Annotation", kser: SerializerT, vser: SerializerT):
    name = f"{util.get_name(annotation.resolved_origin)}KVSerDict"
    bases = (KVSerDict,)
    omit = (*annotation.serde.omit_values,)

    def getitem(self, key):
        v = dict.__getitem__(self, key)
        return self.__missing__(key) if v is Unprocessed else v

    if omit:

        def missing(self, key, *, __repr=util.collectionrepr, __vser=vser, __omit=omit):
            if key in self._unprocessed:
                value = self._unprocessed[key]
                if value in __omit:
                    return Omit
                newv = __vser(  # type: ignore
                    value, lazy=self.lazy, name=__repr(self._name, key),
                )
                self[key] = newv
                return newv
            raise KeyError(f"{__repr(self._name, key)!r}")

        def iter(self, *, Omit=Omit, __kser=kser):  # type: ignore
            for k in self._unprocessed:
                if self[k] is Omit:
                    continue
                yield k

    else:

        def missing(self, key, *, __repr=util.collectionrepr, __vser=vser):  # type: ignore
            if key in self._unprocessed:
                newv = vser(  # type: ignore
                    self._unprocessed[key],
                    lazy=self.lazy,
                    name=__repr(self._name, key),
                )
                self[key] = newv
                return newv
            raise KeyError(f"{__repr(self._name, key)!r}")

        def iter(self, *, __kser=kser):  # type: ignore
            for k in self._unprocessed:
                self[k]
                yield k

    stdlib = json.using_stdlib()
    ns = dict(
        type=annotation.generic,
        lazy=False,
        kser=staticmethod(kser),
        vser=staticmethod(vser),
        omit=omit,
        __missing__=missing,
        __iter__=iter,
        stdlib=stdlib,
    )
    if stdlib:
        ns["__getitem__"] = getitem
    return type(name, bases, ns)


class KVSerDict(dict):
    kser: SerializerT
    vser: SerializerT
    lazy: bool
    omit: Iterable[Any]
    stdlib: bool

    __slots__ = ("_unprocessed", "_name")

    def __init__(self, mapping: Mapping, *, lazy: bool = False, __tfname__: util.ReprT):
        kser = self.kser
        self._name = __tfname__
        self._unprocessed = {kser(k): v for k, v in mapping.items()}  # type: ignore
        self.lazy = lazy
        if self.stdlib:
            dict.__init__(self, dict.fromkeys(self._unprocessed, Unprocessed))

    def items(self) -> ItemsView[KT, VT]:  # pragma: nocover
        return ItemsView(self)  # type: ignore

    def keys(self) -> KeysView[KT]:
        return KeysView(self)  # type: ignore

    def values(self) -> ValuesView[VT]:  # pragma: nocover
        return ValuesView(self)  # type: ignore


def make_serlist(annotation: "Annotation", serializer: SerializerT):
    name = f"{util.get_name(annotation.resolved_origin)}SerList"
    bases = (SerList,)
    ns = dict(
        lazy=False,
        serializer=staticmethod(serializer),
        omit=(*annotation.serde.omit_values,),
    )
    return type(name, bases, ns)


class SerList(list):
    serializer: SerializerT
    omit: Iterable[Any]
    lazy: bool

    __slots__ = ("repr", "_name")

    def __init__(self, seq=(), *, __tfname__: util.ReprT, lazy: bool = False):
        self.repr = util.collectionrepr
        self.lazy = lazy
        self._name = __tfname__
        ser = self.serializer
        list.__init__(
            self,
            (
                ser(x, lazy=lazy, name=self.repr(self._name, i))  # type: ignore
                for i, x in enumerate(seq)
            ),
        )

    def __setitem__(self, key, value):  # pragma: nocover
        super().__setitem__(
            key,
            self.serializer(value, lazy=self.lazy, name=self.repr(self._name, key)),
        )

    def append(self, object: _T) -> None:  # pragma: nocover
        super().append(
            self.serializer(  # type: ignore
                object, lazy=self.lazy, name=self.repr(self._name, len(self)),
            )
        )


def _iso(o) -> str:
    if isinstance(o, (datetime.datetime, datetime.time)) and not o.tzinfo:
        return f"{o.isoformat()}+00:00"
    return o.isoformat()


_decode = methodcaller("decode", DEFAULT_ENCODING)
_total_secs = methodcaller("total_seconds")
_pattern = attrgetter("pattern")


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
    _PRIMITIVES = (str, int, bool, float, type(None), type(...))
    _DYNAMIC = frozenset(
        {Union, Any, inspect.Parameter.empty, dataclasses.MISSING, ClassVar}
    )
    _FNAME = "fname"

    def __init__(self, resolver: "Resolver"):
        self.resolver = resolver
        self._serializer_cache: MutableMapping[str, SerializerT] = {}

    @staticmethod
    def _get_name(annotation: "Annotation") -> str:
        return util.get_defname("serializer", annotation)

    def _check_add_null_check(self, func: gen.Block, annotation: "Annotation"):
        if annotation.optional:
            with func.b(f"if o in {self.resolver.OPTIONALS}:") as b:
                b.l(f"{gen.Keyword.RET}")

    def _add_type_check(self, func: gen.Block, annotation: "Annotation"):
        resolved_name = util.get_name(annotation.resolved)
        func.l(f"{self._FNAME} = name or {resolved_name!r}")
        line = "if not tcheck(o.__class__, t):"
        check: Callable[[Any], bool] = util.cached_issubclass
        if checks.isbuiltinsubtype(annotation.generic):
            line = "if not tcheck(o, t):"
            check = isinstance  # type: ignore
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
                t=annotation.generic,
            )

    def _build_list_serializer(
        self, func: gen.Block, annotation: "Annotation",
    ):
        # Check for value types
        line = "[*o]"
        ns: Dict[str, Any] = {}
        if annotation.args:
            arg_a: "Annotation" = self.resolver.annotation(
                annotation.args[0], flags=annotation.serde.flags
            )
            arg_ser = self.factory(arg_a)
            arg_ser_name = "arg_ser"

            serlist = make_serlist(annotation, arg_ser)
            serlist_name = serlist.__name__

            ns = {serlist_name: serlist, arg_ser_name: arg_ser}
            line = f"{serlist_name}(o, lazy=lazy, __tfname__={self._FNAME})"

        self._check_add_null_check(func, annotation)
        self._add_type_check(func, annotation)
        func.l(f"{gen.Keyword.RET} {line}", level=None, **ns)

    def _build_key_serializer(
        self, name: str, kser: SerializerT, annotation: "Annotation"
    ) -> SerializerT:
        kser_name = util.get_name(kser)
        # Build the namespace
        ns: Dict[str, Any] = {
            kser_name: kser,
        }
        kvar = "k_"
        with gen.Block(ns) as main:
            with main.f(
                name, main.param(kvar), main.param("lazy", default=False)
            ) as kf:
                k = f"{kser_name}({kvar})"
                # If there are args & field mapping, get the correct field name
                # AND serialize the key.
                if annotation.serde.fields_out:
                    ns["fields_out"] = annotation.serde.fields_out
                    k = f"{kser_name}(fields_out.get({kvar}, {kvar}))"
                # If there are only serializers, get the serialized value
                if annotation.serde.flags.case:
                    ns.update(case=annotation.serde.flags.case.transformer)
                    k = f"case({k})"
                kf.l(f"{gen.Keyword.RET} {k}")
        return main.compile(name=name, ns=ns)

    def _finalize_mapping_serializer(
        self, func: gen.Block, serdict: Type, annotation: "Annotation",
    ):
        serdict_name = serdict.__name__
        self._check_add_null_check(func, annotation)
        self._add_type_check(func, annotation)

        ns: Dict[str, Any] = {serdict_name: serdict}
        func.l(
            f"d = {serdict_name}(o, lazy=lazy, __tfname__={self._FNAME})",
            level=None,
            **ns,
        )
        # Write the line.
        line = "d if lazy else {**d}"
        func.l(f"{gen.Keyword.RET} {line}")

    def _build_dict_serializer(self, func: gen.Block, annotation: "Annotation"):
        # Check for args
        kser_: SerializerT
        vser_: SerializerT
        kser_, vser_ = self.resolver.primitive, self.resolver.primitive
        args = util.get_args(annotation.resolved)
        if args:
            kt, vt = args
            ktr: "Annotation" = self.resolver.annotation(
                kt, flags=annotation.serde.flags
            )
            vtr: "Annotation" = self.resolver.annotation(
                vt, flags=annotation.serde.flags
            )
            kser_, vser_ = (self.factory(ktr), self.factory(vtr))
        kser_ = self._build_key_serializer(f"{func.name}_kser", kser_, annotation)
        # Get the names for our important variables

        serdict = make_kv_serdict(annotation, kser_, vser_)

        self._finalize_mapping_serializer(func, serdict, annotation)

    def _build_class_serializer(
        self, func: gen.Block, annotation: "Annotation",
    ):
        # Get the field serializers
        fields_ser = {x: self.factory(y) for x, y in annotation.serde.fields.items()}

        serdict = make_class_serdict(annotation, fields_ser)

        self._finalize_mapping_serializer(func, serdict, annotation)

    def _compile_enum_serializer(self, annotation: "Annotation",) -> SerializerT:
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

            return serializer
        # Else default to lazy serialization
        return self.resolver.primitive

    def _compile_defined_serializer(
        self, annotation: "Annotation", ser: SerializerT,
    ) -> SerializerT:
        func_name = self._get_name(annotation)
        ser_name = "ser"
        ns = {ser_name: ser}
        with gen.Block(ns) as main:
            with main.f(
                func_name,
                main.param("o"),
                main.param("lazy", default=False),
                main.param("name", default=None),
            ) as func:
                self._check_add_null_check(func, annotation)
                self._add_type_check(func, annotation)
                line = f"{ser_name}(o)"
                if annotation.origin in (type(o) for o in self.resolver.OPTIONALS):
                    line = "None"
                func.l(f"{gen.Keyword.RET} {line}")

        serializer: SerializerT = main.compile(name=func_name, ns=ns)
        return serializer

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
        origin = annotation.resolved_origin
        # Lazy shortcut for messy paths (Union, Any, ...)
        if origin in self._DYNAMIC or not annotation.static:
            serializer = self.resolver.primitive
        # Enums are special
        elif checks.isenumtype(annotation.resolved):
            serializer = self._compile_enum_serializer(annotation)
        # Primitives don't require further processing.
        # Just check for nullable and the correct type.
        elif origin in self._PRIMITIVES:
            ns: dict = {}
            with gen.Block(ns) as main:
                with main.f(
                    func_name,
                    main.param("o"),
                    main.param("lazy", default=False),
                    main.param("name", default=None),
                ) as func:
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
                with main.f(
                    func_name,
                    main.param("o"),
                    main.param("lazy", default=False),
                    main.param("name", default=None),
                ) as func:
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
