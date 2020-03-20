import dataclasses
import datetime
import decimal
import enum
import inspect
import ipaddress
import pathlib
import re
import uuid
from collections import deque
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
    Tuple,
    ItemsView,
    KeysView,
    ValuesView,
    Deque,
    Dict,
)

from typic import util, checks, gen, types
from typic.common import DEFAULT_ENCODING
from .common import SerializerT, SerdeConfig, Annotation

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver


_T = TypeVar("_T")
KT = TypeVar("KT")
VT = TypeVar("VT")
KVPairT = Tuple[KT, VT]


def make_class_serdict(annotation: "Annotation", fields: Mapping[str, SerializerT]):
    name = f"{util.get_name(annotation.origin)}SerDict"
    bases = (ClassFieldSerDict,)
    ns = dict(
        lazy=False,
        getters=annotation.serde.fields_getters,
        fields=fields,
        fields_out=annotation.serde.fields_out,
        omit=(*annotation.serde.omit_values,),
    )
    return type(name, bases, ns)


class ClassFieldSerDict(dict):
    instance: Any
    lazy: bool
    getters: Mapping[str, Callable[[str], Any]]
    fields: Mapping[str, SerializerT]
    fields_out: Mapping[str, str]
    omit: Iterable[Any]
    _unprocessed: Deque[str]

    def __init__(self, instance: Any, lazy: bool = False):
        super().__init__({})
        self._unprocessed = deque(self.fields_out)
        self.instance = instance
        self.lazy = lazy

    def __hash__(self):  # pragma: nocover
        h = getattr(self.instance, "__hash__", None)
        return h() if h else None

    def __process_iter__(self):
        _up = self._unprocessed
        _uppop = self._unprocessed.popleft
        _f = self.fields
        _fget = _f.__getitem__
        _foutget = self.fields_out.__getitem__
        _omit = self.omit
        _inst = self.instance
        _gettersget = self.getters.__getitem__
        _lazy = self.lazy
        setitem = super().__setitem__
        while _up:
            name = _uppop()
            getter = _gettersget(name)
            value = getter(_inst)
            if value in _omit:
                continue
            ser = _fget(name)
            name = _foutget(name)
            setitem(name, ser(value, lazy=_lazy))
            yield name

    def __iter__(self):
        yield from super().__iter__()
        if self._unprocessed:
            yield from self.__process_iter__()

    def __getitem__(self, item):
        if item in self._unprocessed:  # pragma: nocover
            ser = self.fields[item]
            getter = self.getters[item]
            v = ser(getter(self.instance), lazy=self.lazy)
            self._unprocessed.remove(item)
            item = self.fields_out.get(item, item)
            self[item] = v
            return v
        return super().__getitem__(item)

    def items(self) -> ItemsView[KT, VT]:  # pragma: nocover
        return ItemsView(self)  # type: ignore

    def keys(self) -> KeysView[KT]:  # pragma: nocover
        return KeysView(self)  # type: ignore

    def values(self) -> ValuesView[VT]:  # pragma: nocover
        return ValuesView(self)  # type: ignore


def make_kv_serdict(annotation: "Annotation", kser: SerializerT, vser: SerializerT):
    name = f"{util.get_name(annotation.origin)}KVSerDict"
    bases = (KVSerDict,)
    ns = dict(
        lazy=False,
        kser=staticmethod(kser),
        vser=staticmethod(vser),
        omit=(*annotation.serde.omit_values,),
    )
    return type(name, bases, ns)


class KVSerDict(dict):
    kser: SerializerT
    vser: SerializerT
    lazy: bool
    omit: Iterable[Any]
    _unprocessed: Dict[str, Any]

    def __init__(self, seq=None, *, lazy: bool = False, **kwargs):
        super().__init__({})
        self._unprocessed = {**(seq or {}), **kwargs}
        self.lazy = lazy

    def __process_iter__(self):
        _up = self._unprocessed
        _kser = self.kser
        _vser = self.vser
        _omit = self.omit
        _lazy = self.lazy
        popitem = self._unprocessed.popitem
        setitem = super().__setitem__
        while _up:
            k, v = popitem()
            if v in _omit:
                continue
            k, v = _kser(k), _vser(v, lazy=_lazy)
            setitem(k, v)
            yield k

    def __getitem__(self, item) -> VT:
        if item in self._unprocessed:  # pragma: nocover
            item, v = (
                self.kser(item),  # type: ignore
                self.vser(self._unprocessed.pop(item), lazy=self.lazy),  # type: ignore
            )
            self[item] = v
            return v
        return super().__getitem__(item)

    def __setitem__(self, key, value):  # pragma: nocover
        self._unprocessed[key] = value

    def __iter__(self):
        yield from super().__iter__()
        if self._unprocessed:
            yield from self.__process_iter__()

    def items(self) -> ItemsView[KT, VT]:  # pragma: nocover
        return ItemsView(self)  # type: ignore

    def keys(self) -> KeysView[KT]:
        return KeysView(self)  # type: ignore

    def values(self) -> ValuesView[VT]:  # pragma: nocover
        return ValuesView(self)  # type: ignore


def make_serlist(annotation: "Annotation", serializer: SerializerT):
    name = f"{util.get_name(annotation.origin)}SerList"
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
    _unprocessed: Deque[Any]

    def __init__(self, seq=(), *, lazy: bool = False):
        self.lazy = lazy
        self._unprocessed = deque(seq)
        super().__init__(seq)

    def __process_iter__(self):
        _up = self._unprocessed
        _uppop = _up.popleft
        _s = self.serializer
        _omit = self.omit
        _lazy = self.lazy
        setitem = super().__setitem__
        ix = 0
        remove = super().remove
        removals = set()
        remadd = removals.add
        while _up:
            v = _uppop()
            if v in _omit:
                remadd(v)
                continue
            v = _s(v, lazy=_lazy)
            setitem(ix, v)
            yield v
            ix += 1
        for v in removals:
            remove(v)

    def __iter__(self):
        if self._unprocessed:
            return self.__process_iter__()
        return super().__iter__()

    def __getitem__(self, item):  # pragma: nocover
        [*self.__process_iter__()]
        return super().__getitem__(item)

    def __len__(self):
        return len(self._unprocessed) + super().__len__()

    def __setitem__(self, key, value):  # pragma: nocover
        super().__setitem__(key, self.serializer(value, lazy=self.lazy))

    def append(self, object: _T) -> None:  # pragma: nocover
        super().append(self.serializer(object, lazy=self.lazy))  # type: ignore


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
        line = "[*o]"
        ns: Dict[str, Any] = {}
        if annotation.args:
            arg_a: "Annotation" = self.resolver.annotation(
                annotation.args[0], flags=annotation.serde.flags
            )
            arg_ser = self.factory(arg_a)
            arg_ser_name = f"arg_ser"

            serlist = make_serlist(annotation, arg_ser)
            serlist_name = serlist.__name__

            ns = {serlist_name: serlist, arg_ser_name: arg_ser}
            func.l(f"l = {serlist_name}(o, lazy=lazy)")
            line = f"l if lazy else [*l]"

        if annotation.optional:
            line = f"o if o is None else ({line})"
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

    @staticmethod
    def _finalize_mapping_serializer(
        func: gen.Block, serdict: Type, annotation: "Annotation"
    ):
        serdict_name = serdict.__name__
        if annotation.optional:
            with func.b("if o is None:") as b:
                b.l(f"{gen.Keyword.RET}")
        ns: Dict[str, Any] = {serdict_name: serdict}
        func.l(f"d = {serdict_name}(o, lazy=lazy)", level=None, **ns)
        # Write the line.
        line = f"d if lazy else {{**d}}"
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
        origin: Type[enum.Enum] = cast(
            Type[enum.Enum], util.origin(annotation.resolved)
        )
        ts = {type(x.value) for x in origin}
        # If we can predict a single type the return the serializer for that
        if len(ts) == 1:
            t = ts.pop()
            va = self.resolver.annotation(t, flags=annotation.serde.flags)
            vser = self.factory(va)

            def serializer(o: enum.Enum, *, lazy: bool = False, _vser=vser):
                return _vser(o.value, lazy=lazy)

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
                func_name, main.param("o"), main.param("lazy", default=False)
            ) as func:
                line = f"{ser_name}(o)"
                if annotation.optional:
                    line = f"o if o is None else {line}"
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
        origin = util.origin(annotation.resolved)
        # Lazy shortcut for messy paths (Union, Any, ...)
        if origin in self._DYNAMIC or not annotation.static:
            serializer = self.resolver.primitive
        # Enums are special
        elif checks.isenumtype(annotation.resolved):
            serializer = self._compile_enum_serializer(annotation)
        # Primitives don't require further processing.
        elif origin in self._PRIMITIVES:

            def serializer(o: _T, lazy: bool = False) -> _T:
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
            with gen.Block(ns) as main:
                with main.f(
                    func_name, main.param("o"), main.param("lazy", default=False)
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
