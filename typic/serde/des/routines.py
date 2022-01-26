from __future__ import annotations

import dataclasses
import datetime
import functools
import inspect
import re
import uuid
import types
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    cast,
    Union,
    Any,
    Tuple,
    Callable,
    Mapping,
    TypeVar,
    Collection,
)

from pendulum import parse as dateparse

from typic import checks
from typic import common
from typic.compat import Generic, TypeGuard
from typic.serde.common import Annotation, DelayedAnnotation, ForwardDelayedAnnotation
from typic.util import (
    slotted,
    fromstr,
    get_tag_for_types,
    TaggedUnion,
    cached_signature,
)

if TYPE_CHECKING:
    from typic.serde.common import DeserializerT, SerdeProtocol
    from typic.serde.resolver import Resolver


__all__ = (
    "BaseRoutine",
    "CollectionRoutine",
    "DateRoutine",
    "DateTimeRoutine",
    "FieldsRoutine",
    "FixedTupleRoutine",
    "LiteralRoutine",
    "MappingRoutine",
    "PatternRoutine",
    "SimpleRoutine",
    "TextRoutine",
    "TimeRoutine",
    "TimeDeltaRoutine",
    "UnionRoutine",
    "UUIDRoutine",
)

_T = TypeVar("_T")


@slotted(dict=False, weakref=True)
@dataclasses.dataclass
class BaseRoutine(Generic[_T]):
    annotation: Annotation[type[_T]]
    resolver: Resolver
    namespace: type | None = None

    def deserializer(self) -> DeserializerT[_T]:
        check = self._get_checks()
        deser = self._get_deserializer()

        def deserializer(val, *, __check=check, __deserialize=deser) -> _T:
            value, valid = __check(val)
            if valid:
                return value
            return __deserialize(value)

        return cast("DeserializerT", deserializer)

    def _get_deserializer(self) -> DeserializerT[_T]:
        ...

    def _get_checks(self) -> _CheckT:
        annotation = self.annotation
        rorigin = annotation.resolved_origin
        nullable = annotation.optional
        defaults = (
            annotation.has_default
            and annotation.parameter.default not in self.resolver.OPTIONALS
        )
        evaluate = self._get_evaluate()
        if hasattr(rorigin, self._EQUALITY_FUNC):
            return self._get_custom_eq_checks(
                evaluate=evaluate, nullable=nullable, defaults=defaults
            )

        if annotation.args:
            return self._get_subscripted_eq_checks(
                evaluate=evaluate, nullable=nullable, defaults=defaults
            )

        return self._get_standard_eq_checks(
            evaluate=evaluate, nullable=nullable, defaults=defaults
        )

    def _get_evaluate(self) -> _EvaluateT:
        rorigin = cast(type, self.annotation.resolved_origin)
        # Determine whether we should try evaluating a string input.
        # If the type we're coercing to is a string-like or decimal, don't evaluate.
        if inspect.isclass(rorigin) and (
            issubclass(rorigin, (str, bytes)) or checks.isdecimaltype(rorigin)
        ):

            def evaluate_for_str(o):
                return o

            return evaluate_for_str

        def evaluate(o, *, __fromstr=fromstr):
            if isinstance(o, str):
                return __fromstr(o)
            return o

        return evaluate

    def _get_standard_eq_checks(
        self,
        *,
        evaluate: Callable,
        nullable: bool,
        defaults: bool,
    ) -> _CheckT:
        rorigin = self.annotation.resolved_origin
        default = self.annotation.parameter.default
        if (nullable, defaults) == (True, True):

            def check_nullable_defaults(
                o,
                *,
                __eval=evaluate,
                __default=default,
                __type=rorigin,
            ):
                e = __eval(o)
                ecls = e.__class__
                return e, (
                    e is None
                    or e is ...
                    or (e == __default and ecls is __type)
                    or ecls is __type
                )

            return check_nullable_defaults

        if (nullable, defaults) == (True, False):

            def check_nullable(
                o,
                *,
                __eval=evaluate,
                __type=rorigin,
            ):
                e = __eval(o)
                return e, (e is None or e is ... or e.__class__ is __type)

            return check_nullable

        if (nullable, defaults) == (False, True):

            def check_default(
                o,
                *,
                __eval=evaluate,
                __default=default,
                __type=rorigin,
            ):
                e = __eval(o)
                ecls = e.__class__
                return e, ((e == __default and ecls is __type) or ecls is __type)

            return check_default

        def check_type(
            o,
            *,
            __eval=evaluate,
            __type=rorigin,
        ):
            e = __eval(o)
            return e, (e.__class__ is __type)

        return check_type

    def _get_subscripted_eq_checks(
        self,
        *,
        evaluate: Callable,
        nullable: bool,
        defaults: bool,
    ) -> _CheckT:
        default = self.annotation.parameter.default
        if (nullable, defaults) == (True, True):

            def check_nullable_default(
                o,
                *,
                __eval=evaluate,
                __default=default,
            ):
                e = __eval(o)
                return e, (e is None or e is ... or e == __default)

            return check_nullable_default

        if (nullable, defaults) == (True, False):

            def check_nullable(
                o,
                *,
                __eval=evaluate,
            ):
                e = __eval(o)
                return e, (e is None or e is ...)

            return check_nullable

        if (nullable, defaults) == (False, True):

            def check_defaults(
                o,
                *,
                __eval=evaluate,
                __default=default,
            ):
                e = __eval(o)
                return e, (e == __default)

            return check_defaults

        def check_eval(
            o,
            *,
            __eval=evaluate,
        ):
            e = __eval(o)
            return e, False

        return check_eval

    def _get_custom_eq_checks(
        self,
        *,
        evaluate: Callable,
        nullable: bool,
        defaults: bool,
    ) -> _CheckT:
        default = self.annotation.parameter.default
        rorigin = self.annotation.resolved_origin
        default_custom_eq = hasattr(default, self._EQUALITY_FUNC)
        if (nullable, defaults) == (True, True):
            default = self.annotation.parameter.default
            if default_custom_eq:

                def check_nullable_defaults_custom_eq(
                    o,
                    *,
                    __eval=evaluate,
                    __default=default,
                    __type=rorigin,
                ):
                    e = __eval(o)
                    return e, (
                        e is None
                        or e is ...
                        or e.__class__ == __type
                        or __default.equals(e)
                    )

                return check_nullable_defaults_custom_eq

            def check_nullable_defaults(
                o,
                *,
                __eval=evaluate,
                __default=default,
                __equality_func=self._EQUALITY_FUNC,
                __type=rorigin,
            ):
                e = __eval(o)
                _custom_eq = hasattr(e, __equality_func)
                if _custom_eq:
                    return e, (
                        e is None
                        or e is ...
                        or e.__class__ is __type
                        or e.equals(__default)
                    )
                return e, (
                    e is None or e is ... or e.__class__ is __type or e == __default
                )

            return check_nullable_defaults

        if (nullable, defaults) == (True, False):

            def check_nullable(
                o,
                *,
                __eval=evaluate,
                __type=rorigin,
            ):
                e = __eval(o)
                return e, (e is None or e is ... or e.__class__ is __type)

            return check_nullable

        if (nullable, defaults) == (False, True):
            if default_custom_eq:

                def check_defaults_custom_eq(
                    o,
                    *,
                    __eval=evaluate,
                    __default=default,
                    __equality_func=self._EQUALITY_FUNC,
                    __type=rorigin,
                ):
                    e = __eval(o)
                    return e, e.__class__ is rorigin or __default.equals(e)

                return check_defaults_custom_eq

            def check_defaults(
                o,
                *,
                __eval=evaluate,
                __default=default,
                __optionals=frozenset(self.resolver.OPTIONALS),
                __equality_func=self._EQUALITY_FUNC,
                __type=self.annotation.resolved_origin,
            ):
                e = __eval(o)
                _custom_eq = hasattr(e, __equality_func)
                if _custom_eq:
                    return e, (e.__class__ is __type or e.equals(__default))
                return e, (e.__class__ is __type or e == __default)

            return check_defaults

        def check_eval(
            o,
            *,
            __eval=evaluate,
            __type=self.annotation.resolved_origin,
        ):
            e = __eval(o)
            return e, (e.__class__ is __type)

        return check_eval

    _EQUALITY_FUNC = "equals"


_CheckT = Callable[..., Tuple[Any, TypeGuard[_T]]]
_EvaluateT = Callable[..., Any]


class SimpleRoutine(BaseRoutine[_T]):
    def _get_deserializer(self) -> DeserializerT[_T]:
        rorigin = self.annotation.resolved_origin
        if rorigin is defaultdict:
            rorigin = cast("type[_T]", functools.partial(rorigin, None))
        return cast("DeserializerT", rorigin)


_Text = TypeVar("_Text", str, bytes, bytearray)


class TextRoutine(BaseRoutine[_Text]):
    def _get_deserializer(self) -> DeserializerT[_Text]:
        annotation = self.annotation
        rorigin: type[_Text] = annotation.resolved_origin
        if issubclass(rorigin, bytes):

            def bytes_deserializer(val: Any, *, __origin=rorigin) -> bytes:
                if isinstance(val, str):
                    return val.encode()
                return __origin(val)

            return cast("DeserializerT", bytes_deserializer)

        if issubclass(rorigin, bytearray):

            def bytearray_deserializer(val: Any, *, __origin=rorigin) -> bytearray:
                if isinstance(val, str):
                    return __origin(val, encoding=common.DEFAULT_ENCODING)
                return __origin(val)

            return cast("DeserializerT", bytearray_deserializer)

        def str_deserializer(val: Any, *, __origin=rorigin) -> str:
            if isinstance(val, bytes):
                return val.decode()
            return __origin(val)

        return cast("DeserializerT", str_deserializer)


class DateRoutine(BaseRoutine[datetime.date]):
    def _get_deserializer(self) -> DeserializerT:
        annotation = self.annotation
        rorigin: type[datetime.date] = annotation.resolved_origin

        def date_deserializer(
            val: Any, *, __origin=rorigin, __parse=dateparse
        ) -> datetime.date:
            if isinstance(val, (int, float)):
                return rorigin.fromtimestamp(val)
            date = val
            if isinstance(val, str):
                date = __parse(val, exact=True)

            if date.__class__ is __origin:
                return date

            return __origin(year=date.year, month=date.month, day=date.day)

        return cast("DeserializerT", date_deserializer)


class DateTimeRoutine(BaseRoutine[datetime.datetime]):
    def _get_deserializer(self) -> DeserializerT:
        annotation = self.annotation
        rorigin: type[datetime.datetime] = annotation.resolved_origin

        def datetime_deserializer(
            val: Any, *, __origin=rorigin, __parse=dateparse
        ) -> datetime.datetime:
            if isinstance(val, (int, float)):
                return __origin.fromtimestamp(val)
            dt = val
            if isinstance(val, str):
                dt = __parse(val)

            cls = dt.__class__
            if cls is __origin:
                return dt

            if issubclass(cls, datetime.datetime):
                return __origin(
                    year=dt.year,
                    month=dt.month,
                    day=dt.day,
                    hour=dt.hour,
                    minute=dt.minute,
                    second=dt.second,
                    microsecond=dt.microsecond,
                    tzinfo=dt.tzinfo,
                    fold=dt.fold,
                )

            return __origin(year=dt.year, month=dt.month, day=dt.day)

        return cast("DeserializerT", datetime_deserializer)


class TimeRoutine(BaseRoutine[datetime.time]):
    def _get_deserializer(self) -> DeserializerT[datetime.time]:
        annotation = self.annotation
        rorigin: type[datetime.time] = annotation.resolved_origin

        def time_deserializer(
            val: Any, *, __origin=rorigin, __parse=dateparse
        ) -> datetime.time:
            if isinstance(val, (int, float)):
                return __origin(int(val))
            time = val
            if isinstance(val, (str, bytes)):
                time = __parse(val, exact=True)

            if isinstance(time, datetime.datetime):
                time = time.time()
            elif isinstance(time, datetime.date):
                time = __origin(0)

            if time.__class__ is __origin:
                return time

            return __origin(
                hour=time.hour,
                minute=time.minute,
                second=time.second,
                microsecond=time.microsecond,
                tzinfo=time.tzinfo,
                fold=time.fold,
            )

        return cast("DeserializerT", time_deserializer)


class TimeDeltaRoutine(BaseRoutine[datetime.timedelta]):
    def _get_deserializer(self) -> DeserializerT:
        annotation = self.annotation
        rorigin: type[datetime.timedelta] = annotation.resolved_origin

        def timedelta_deserializer(
            val: Any, *, __origin=rorigin, __parse=dateparse
        ) -> datetime.timedelta:
            if isinstance(val, (int, float)):
                return __origin(int(val))
            td = val
            if isinstance(val, (str, bytes)):
                td = __parse(val, exact=True)

            if td.__class__ is __origin:
                return td

            return __origin(
                days=td.days,
                seconds=td.seconds,
                microseconds=td.microseconds,
                minutes=td.minutes,
                hours=td.hours,
                weeks=td.weeks,
            )

        return cast("DeserializerT", timedelta_deserializer)


class UUIDRoutine(BaseRoutine[uuid.UUID]):
    def _get_deserializer(self) -> DeserializerT[uuid.UUID]:
        annotation = self.annotation
        rorigin: type[uuid.UUID] = annotation.resolved_origin

        def uuid_deserializer(val: Any, *, __origin=rorigin) -> uuid.UUID:

            if isinstance(val, int):
                return __origin(int=val)
            if isinstance(val, bytes):
                return __origin(bytes=val)
            if isinstance(val, tuple):
                return __origin(fields=val)
            if isinstance(val, uuid.UUID):
                return __origin(int=val.int)

            return __origin(val)

        return cast("DeserializerT", uuid_deserializer)


class PatternRoutine(BaseRoutine[re.Pattern]):
    def _get_deserializer(self) -> DeserializerT[re.Pattern]:
        annotation = self.annotation
        rorigin: type[re.Pattern] = annotation.resolved_origin

        def pattern_deserializer(val: Any, *, __origin=rorigin) -> re.Pattern:
            if issubclass(val.__class__, __origin):
                return val
            return re.compile(val)

        return cast("DeserializerT", pattern_deserializer)


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class MappingRoutine(BaseRoutine[Mapping[_KT, _VT]]):
    def _get_deserializer(self) -> DeserializerT[Mapping[_KT, _VT]]:
        rorigin = self.annotation.resolved_origin
        if rorigin is dict:
            return self._get_dict_desrializer()
        ktype, vtype = Any, Any
        if self.annotation.args:
            ktype, vtype = self.annotation.args
        flags = self.annotation.serde.flags
        fields_in = self.annotation.serde.fields_in
        aliased = fields_in.keys() != {*fields_in.values()}
        namespace = self.namespace or rorigin
        kproto: SerdeProtocol = self.resolver.resolve(
            ktype, flags=flags, namespace=namespace  # type: ignore[arg-type]
        )
        vproto: SerdeProtocol = self.resolver.resolve(
            vtype, flags=flags, namespace=namespace  # type: ignore[arg-type]
        )
        kdeser, vdeser = kproto.transmute, vproto.transmute

        if issubclass(rorigin, defaultdict):
            factory = self._get_default_factory()
            rorigin = cast(
                "type[Mapping[_KT, _VT]]", functools.partial(rorigin, factory)
            )

        if aliased:

            def aliased_mapping_deserializer(
                val: Any,
                *,
                __origin=rorigin,
                __k=kdeser,
                __v=vdeser,
                __iter=self.resolver.iterate,
                __aliases=types.MappingProxyType(fields_in),
            ) -> Mapping[_KT, _VT]:
                if checks.ismappingtype(val.__class__):
                    return __origin(
                        (__k(__aliases.get(k, k)), __v(v)) for k, v in val.items()
                    )
                try:
                    return __origin(
                        (__k(__aliases.get(k, k)), __v(v))
                        for k, v in __iter(val, values=True)
                    )
                except (TypeError, ValueError):
                    return __origin(
                        (__k(__aliases.get(k, k)), __v(v)) for k, v in __iter(val)
                    )

            return cast("DeserializerT", aliased_mapping_deserializer)

        def mapping_deserializer(
            val: Any,
            *,
            __origin=rorigin,
            __k=kdeser,
            __v=vdeser,
            __iter=self.resolver.iterate,
        ) -> Mapping[_KT, _VT]:
            if checks.ismappingtype(val.__class__):
                return __origin((__k(k), __v(v)) for k, v in val.items())
            try:
                return __origin((__k(k), __v(v)) for k, v in __iter(val, values=True))
            except (TypeError, ValueError):
                return __origin((__k(k), __v(v)) for k, v in __iter(val))

        return cast("DeserializerT", mapping_deserializer)

    def _get_dict_desrializer(self) -> DeserializerT[dict[_KT, _VT]]:
        rorigin = self.annotation.resolved_origin
        ktype: type[_KT]
        vtype: type[_VT]
        ktype, vtype = Any, Any  # type: ignore
        if self.annotation.args:
            ktype, vtype = self.annotation.args
        flags = self.annotation.serde.flags
        fields_in = self.annotation.serde.fields_in
        aliased = fields_in.keys() != {*fields_in.values()}
        namespace = self.namespace or rorigin
        kproto: SerdeProtocol = self.resolver.resolve(
            ktype, flags=flags, namespace=namespace
        )
        vproto: SerdeProtocol = self.resolver.resolve(
            vtype, flags=flags, namespace=namespace
        )
        kdeser, vdeser = kproto.transmute, vproto.transmute
        if aliased:

            def aliased_dict_deserializer(
                val: Any,
                *,
                __k=kdeser,
                __v=vdeser,
                __iter=self.resolver.iterate,
                __aliases=types.MappingProxyType(fields_in),
            ) -> dict[_KT, _VT]:
                if checks.ismappingtype(val.__class__):
                    return {__k(__aliases.get(k, k)): __v(v) for k, v in val.items()}
                try:
                    return {
                        __k(__aliases.get(k, k)): __v(v)
                        for k, v in __iter(val, values=True)
                    }
                except (TypeError, ValueError):
                    return {__k(__aliases.get(k, k)): __v(v) for k, v in __iter(val)}

            return cast("DeserializerT", aliased_dict_deserializer)

        def dict_deserializer(
            val: Any, *, __k=kdeser, __v=vdeser, __iter=self.resolver.iterate
        ) -> dict[_KT, _VT]:
            if checks.ismappingtype(val.__class__):
                return {__k(k): __v(v) for k, v in val.items()}
            try:
                return {__k(k): __v(v) for k, v in __iter(val, values=True)}
            except (TypeError, ValueError):
                return {__k(k): __v(v) for k, v in __iter(val)}

        return cast("DeserializerT", dict_deserializer)

    def _get_default_factory(self, annotation: Annotation = None):
        annotation = annotation or self.annotation
        factory: type | Callable[..., Any] | None = None
        args: tuple = annotation.args if isinstance(annotation, Annotation) else ()
        if args:
            factory_anno = self.resolver.annotation(args[-1])
            if isinstance(factory_anno, ForwardDelayedAnnotation):
                return factory
            elif isinstance(factory_anno, DelayedAnnotation):
                use = factory_anno.type
                raw = use
            else:
                use = factory_anno.resolved_origin
                raw = factory_anno.un_resolved
            factory = use
            if issubclass(use, defaultdict):
                factory_nested = self._get_default_factory(annotation=factory_anno)

                def factory():
                    return defaultdict(factory_nested)

                factory.__qualname__ = f"factory({repr(raw)})"  # type: ignore

            if not checks.isbuiltinsubtype(use):  # type: ignore

                params: Mapping[str, inspect.Parameter] = cached_signature(
                    use
                ).parameters
                if not any(p.default is p.empty for p in params.values()):

                    def factory(*, __origin=use):
                        return __origin()

                    factory.__qualname__ = f"factory({repr(raw)})"  # type: ignore

        return factory


class CollectionRoutine(BaseRoutine[Collection[_VT]]):
    def _get_deserializer(self) -> DeserializerT[Collection[_VT]]:
        vtype = self.annotation.args[0]
        flags = self.annotation.serde.flags
        rorigin = self.annotation.resolved_origin
        namespace = self.namespace or rorigin
        vdeser = self.resolver.resolve(vtype, flags=flags, namespace=namespace)
        if rorigin is list:

            def list_deserializer(
                val: Any, *, __v=vdeser, __iter=self.resolver.iterate
            ) -> list[_VT]:
                return [__v(v) for v in __iter(val, values=True)]

            return cast("DeserializerT", list_deserializer)

        if rorigin is set:

            def set_deserializer(
                val: Any, *, __v=vdeser, __iter=self.resolver.iterate
            ) -> set[_VT]:
                return {__v(v) for v in __iter(val, values=True)}

            return cast("DeserializerT", set_deserializer)

        if rorigin is frozenset:

            def frozenset_deserializer(
                val: Any, *, __v=vdeser, __iter=self.resolver.iterate
            ) -> frozenset[_VT]:
                return frozenset(__v(v) for v in __iter(val, values=True))

            return cast("DeserializerT", frozenset_deserializer)

        if rorigin is tuple:

            def tuple_deserializer(
                val: Any, *, __v=vdeser, __iter=self.resolver.iterate
            ) -> tuple[_VT, ...]:
                return (*(__v(v) for v in __iter(val, values=True)),)

            return cast("DeserializerT", tuple_deserializer)

        def collection_deserializer(
            val: Any,
            *,
            __origin=rorigin,
            __v=vdeser,
            __iter=self.resolver.iterate,
        ):
            return __origin(__v(v) for v in __iter(val, values=True))

        return cast("DeserializerT", collection_deserializer)


class FixedTupleRoutine(BaseRoutine[Tuple[_VT]]):
    def _get_deserializer(self) -> DeserializerT:
        annotation = self.annotation
        rorigin = self.annotation.resolved_origin
        namespace = self.namespace or rorigin
        _desers = {
            ix: self.resolver.resolve(
                t, flags=annotation.serde.flags, namespace=namespace
            )
            for ix, t in enumerate(annotation.args)
        }
        desers = types.MappingProxyType(_desers)
        if rorigin is tuple:

            def fixed_tuple_deserializer(
                val: Any,
                *,
                __origin=rorigin,
                __desers=desers,
                __iter=self.resolver.iterate,
            ):
                return (
                    *(
                        __desers[ix](v)
                        for ix, v in enumerate(__iter(val, values=True))
                        if ix in __desers
                    ),
                )

            return cast("DeserializerT", fixed_tuple_deserializer)

        def fixed_tuple_sub_deserializer(
            val: Any, *, __origin=rorigin, __desers=desers, __iter=self.resolver.iterate
        ):
            return __origin(
                __desers[ix](v) for ix, v in enumerate(__iter(val, values=True))
            )

        return cast("DeserializerT", fixed_tuple_sub_deserializer)


class FieldsRoutine(BaseRoutine[_T]):
    def _get_deserializer(self) -> DeserializerT[_T]:
        serde = self.annotation.serde
        rorigin = self.annotation.resolved_origin
        matched = frozenset({*serde.fields_in.values()} & serde.fields.keys())
        isaliased = {*serde.fields_in.values()} != serde.fields_in.keys()
        ismatching = len(matched) == len(serde.fields)
        namespace = self.namespace or rorigin
        if isaliased is False:
            _desers = {
                f: p.transmute
                for f, p in self.resolver.protocols(
                    rorigin, signature_only=True
                ).items()
            }

            def fields_deserializer(
                val: Any,
                *,
                __origin=rorigin,
                __desers=types.MappingProxyType(_desers),
                __translate=self.resolver.translate,
            ) -> _T:
                cls = val.__class__
                if checks.ismappingtype(cls):
                    return __origin(
                        **{f: __desers[f](val[f]) for f in val.keys() & __desers.keys()}
                    )
                if not checks.isnamedtuple(cls):
                    if issubclass(cls, (list, set, frozenset, tuple)):
                        return __origin(*val)
                    if checks.isbuiltinsubtype(cls):
                        return __origin(val)
                return __translate(val, __origin)

            return cast("DeserializerT", fields_deserializer)

        if ismatching:
            aliases = types.MappingProxyType(serde.fields_in)
            reversed = {v: k for k, v in aliases.items()}
            _desers = {
                reversed[f]: self.resolver._resolve_from_annotation(
                    serde.fields[f], namespace=namespace
                ).transmute
                for f in matched
            }

        else:
            aliases = types.MappingProxyType(serde.fields_in)
            unmatched = {f: f for f in serde.fields.keys() - matched}
            reversed = {v: k for k, v in aliases.items()}
            reversed.update(unmatched)
            _desers = {
                reversed[f]: self.resolver._resolve_from_annotation(
                    serde.fields[f], namespace=namespace
                ).transmute
                for f in matched | unmatched.keys()
            }

        def aliased_fields_deserializer(
            val: Any,
            *,
            __origin=rorigin,
            __aliases=aliases,
            __desers=types.MappingProxyType(_desers),
            __translate=self.resolver.translate,
            __bind=self.resolver.bind,
        ) -> _T:
            cls = val.__class__
            if checks.ismappingtype(cls):
                return __origin(
                    **{
                        __aliases[f]: __desers[f](v)
                        for f, v in val.keys() & __aliases.keys()
                    }
                )
            isnamedtuple = checks.isnamedtuple(cls)
            if not isnamedtuple and issubclass(cls, (list, set, frozenset, tuple)):
                return __origin(*__bind(__origin, *val).eval())
            if not isnamedtuple and checks.isbuiltinsubtype(cls):
                return __origin(val)
            return __translate(val, __origin)

        return cast("DeserializerT", aliased_fields_deserializer)


class UnionRoutine(BaseRoutine[_T]):
    def _get_deserializer(self) -> DeserializerT[_T]:
        # Get all types which we may coerce to.
        args = (
            *(a for a in self.annotation.args if a not in {None, Ellipsis, type(None)}),
        )
        if not args:
            return cast("DeserializerT", lambda val: val)

        # Get all custom types, which may have discriminators
        targets = (*(a for a in args if not checks.isstdlibtype(a)),)
        # We can only build a tagged union deserializer if all args are valid
        if args != targets:
            return self._get_generic_union_deserializer()

        # Try to collect the field which will be the discriminator.
        # First, get a mapping of Type -> Proto & Type -> Fields
        tagged = get_tag_for_types(targets)
        # Just bail out if we can't find a key.
        if not tagged:
            return self._get_generic_union_deserializer()
        return self._get_tagged_union_deserializer(tagged)

    def _get_generic_union_deserializer(self) -> DeserializerT[_T]:
        args = self.annotation.args
        protos = tuple(
            self.resolver.resolve(a, namespace=self.namespace)
            for a in args
            if a not in {None, Ellipsis, type(None)}
        )

        _desers = {p.annotation.resolved_origin: p.transmute for p in protos}
        desers = types.MappingProxyType(_desers)

        def union_deserializer(val: Any, *, __desers=desers) -> _T:
            cls = val.__class__
            for origin, deser in __desers.items():
                if issubclass(origin, cls):
                    return deser(val)
            for deser in __desers.values():
                try:
                    return deser(val)
                except (TypeError, ValueError, KeyError):
                    pass

            raise ValueError(
                f"Value could not be deserialized into one of {(*__desers,)}: {val!r}"
            )

        return cast("DeserializerT", union_deserializer)

    def _get_tagged_union_deserializer(self, tagged: TaggedUnion) -> DeserializerT[_T]:
        _desers = {
            value: self.resolver.resolve(t, namespace=self.namespace).transmute
            for value, t in tagged.types_by_values
        }
        desers = types.MappingProxyType(_desers)

        def tagged_union_deserializer(
            val: Any,
            *,
            __desers=desers,
            __tag=tagged.tag,
            __types=tagged.types,
            __empty=inspect.Signature.empty,
        ) -> _T:
            cls = val.__class__
            tag = (
                val.get(__tag, __empty)
                if checks.ismappingtype(cls)
                else getattr(val, __tag, __empty)
            )
            if tag in __desers:
                return __desers[tag](val)

            raise ValueError(
                f"Value is missing field {__tag!r} with one of {__types}: {val!r}"
            )

        return cast("DeserializerT", tagged_union_deserializer)


class LiteralRoutine(BaseRoutine[_T]):
    def _get_deserializer(self) -> DeserializerT[_T]:
        annotation = self.annotation
        args = annotation.args
        types: set[type] = {a.__class__ for a in args}
        t = types.pop() if len(types) == 1 else Union[tuple(types)]
        t_anno = cast(
            "Annotation",
            self.resolver.annotation(
                t,  # type: ignore
                name=annotation.parameter.name,
                is_optional=annotation.optional,
                is_strict=annotation.strict,
                flags=annotation.serde.flags,
                default=annotation.parameter.default,
                namespace=self.namespace,
            ),
        )
        return self.resolver.des.factory(t_anno, namespace=self.namespace)
