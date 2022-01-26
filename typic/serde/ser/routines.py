from __future__ import annotations

import dataclasses
import enum
import operator
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    cast,
    Any,
    Callable,
    TypeVar,
    Mapping,
    Collection,
    Iterator,
    Tuple,
)

from typic import checks, common, types
from typic.compat import Generic, TypeGuard
from typic.serde.common import Annotation, PrimitiveT
from typic import util

if TYPE_CHECKING:
    from typic.serde.common import SerializerT
    from typic.serde.resolver import Resolver


_T = TypeVar("_T")


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass
class BaseRoutine(Generic[_T]):
    annotation: Annotation[type[_T]]
    resolver: Resolver
    namespace: type | None = None

    def serializer(self) -> SerializerT[_T]:
        check = self._get_checks()
        ser = self._get_serializer()

        def serializer(
            o: _T,
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __check=check,
            __serialize=ser,
        ) -> PrimitiveT:
            if __check(o, name=name):
                return None
            return __serialize(o, lazy=lazy)

        return cast("SerializerT[_T]", serializer)

    def _get_serializer(self) -> SerializerT[_T]:
        ...

    def _get_checks(self) -> _CheckT:
        generic = self.annotation.generic
        nullable = self.annotation.optional
        if checks.istypeddict(generic):
            generic = dict
        stdlib = False
        tcheck: Callable[..., bool] = util.cached_issubclass
        if checks.isstdlibsubtype(generic):
            tcheck = isinstance
            stdlib = True

        if (nullable, stdlib) == (True, True):

            def nullable_stdlib_check(
                o,
                *,
                name: util.ReprT = None,
                __tcheck=tcheck,
                __optionals=self.resolver.OPTIONALS,
                __t=generic,
                __tname=util.get_name(self.annotation.resolved_origin),
                __qualname=util.get_qualname(self.annotation.generic),
            ) -> bool:
                if o in __optionals:
                    return True
                if tcheck(o, __t):
                    return False
                address = name or __tname
                otname = o.__class__.__name__
                raise SerializationValueError(
                    f"{address}: type {otname!r} is not a subtype "
                    f"of type {__qualname!r}. Perhaps this annotation should be "
                    f"'{__qualname} | {otname}'"
                )

            return cast("_CheckT", nullable_stdlib_check)

        if (nullable, stdlib) == (False, True):

            def stdlib_check(
                o,
                *,
                name: util.ReprT = None,
                __tcheck=tcheck,
                __t=generic,
                __tname=util.get_name(self.annotation.resolved_origin),
                __qualname=util.get_qualname(self.annotation.generic),
            ) -> bool:
                if tcheck(o, __t):
                    return False
                address = name or __tname
                otname = o.__class__.__name__
                raise SerializationValueError(
                    f"{address}: type {otname!r} is not a subtype "
                    f"of type {__qualname!r}. Perhaps this annotation should be "
                    f"'{__qualname} | {otname}'"
                )

            return cast("_CheckT", stdlib_check)

        if (nullable, stdlib) == (True, False):

            def nullable_check(
                o,
                *,
                name: util.ReprT = None,
                __tcheck=tcheck,
                __optionals=self.resolver.OPTIONALS,
                __t=generic,
                __tname=util.get_name(self.annotation.resolved_origin),
                __qualname=util.get_qualname(self.annotation.generic),
            ) -> bool:
                cls = o.__class__
                if o in __optionals:
                    return True
                if tcheck(cls, __t):
                    return False
                address = name or __tname
                otname = cls.__name__
                raise SerializationValueError(
                    f"{address}: type {otname!r} is not a subtype "
                    f"of type {__qualname!r}. Perhaps this annotation should be "
                    f"'{__qualname} | {otname}'"
                )

            return cast("_CheckT", nullable_check)

        def check(
            o,
            *,
            name: util.ReprT = None,
            __tcheck=tcheck,
            __t=generic,
            __tname=util.get_name(self.annotation.resolved_origin),
            __qualname=util.get_qualname(self.annotation.generic),
        ) -> bool:
            cls = o.__class__
            if tcheck(cls, __t):
                return False
            address = name or __tname
            otname = cls.__name__
            raise SerializationValueError(
                f"{address}: type {otname!r} is not a subtype "
                f"of type {__qualname!r}. Perhaps this annotation should be "
                f"'{__qualname} | {otname}'"
            )

        return cast("_CheckT", check)


class BaseCastRoutine(BaseRoutine[_T]):
    def serializer(self) -> SerializerT[_T]:
        check = self._get_checks()
        ser = self._get_serializer()

        def serializer(
            o: _T,
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __check=check,
            __serialize=ser,
        ) -> PrimitiveT:
            if __check(o, name=name):
                return None
            return __serialize(o)

        return cast("SerializerT[_T]", serializer)


class NoopRoutine(BaseCastRoutine[_T]):
    def serializer(self) -> SerializerT[_T]:
        if self.annotation.resolved_origin in self.resolver.OPTIONALS:

            def null_noop_serializer(
                o: _T,
                *,
                name: util.ReprT = None,
                lazy: bool = False,
            ) -> None:
                return None

            return cast("SerializerT[_T]", null_noop_serializer)

        checks = self._get_checks()

        def noop_serializer(
            o: PrimitiveT,
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __check=checks,
        ) -> PrimitiveT | None:
            if __check(o):
                return None
            return o

        return cast("SerializerT[_T]", noop_serializer)


class CastRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        return cast("SerializerT[_T]", self.namespace)


class StringRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        return cast("SerializerT[_T]", str)


class PatternRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        return cast("SerializerT[_T]", _pattern)


class ISOFormatRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        return cast("SerializerT[_T]", util.isoformat)


class SecretRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        if issubclass(self.annotation.resolved_origin, types.SecretBytes):
            return cast(
                "SerializerT[_T]", lambda o, *, __decode=_decode: __decode(o.secret)
            )
        return cast("SerializerT[_T]", _secret)


class BytesRoutine(BaseCastRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        return cast("SerializerT[_T]", _decode)


_VT = TypeVar("_VT")


class ListRoutine(BaseRoutine[Collection[_VT]]):
    def _get_serializer(self) -> SerializerT[_T]:
        annotation = self.annotation
        arg_ser: SerializerT[_VT] = cast("SerializerT[_VT]", self.resolver.primitive)
        if annotation.args:
            arg_a = cast(
                "Annotation[_VT]",
                self.resolver.annotation(
                    annotation.args[0], flags=annotation.serde.flags
                ),
            )
            arg_ser = self.resolver.ser.factory(arg_a)

        if annotation.serde.flags.omit:
            omit = tuple(annotation.serde.flags.omit)

            def list_filter_serializer(
                o: Collection[_VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __args=arg_ser,
                __omit=omit,
            ) -> list[PrimitiveT] | Iterator[PrimitiveT]:
                return (
                    (__args(v) for v in o if v not in __omit)
                    if lazy
                    else [__args(v) for v in o if v not in __omit]
                )

            return cast("SerializerT[_T]", list_filter_serializer)

        def list_serializer(
            o: Collection[_VT],
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __args=arg_ser,
        ) -> list[PrimitiveT] | Iterator[PrimitiveT]:
            return (__args(v) for v in o) if lazy else [__args(v) for v in o]

        return cast("SerializerT[_T]", list_serializer)


_KT = TypeVar("_KT")


class DictSerializer(BaseRoutine[Mapping[_KT, _VT]]):
    def _get_serializer(self) -> SerializerT[_T]:
        annotation = self.annotation
        kser_: SerializerT
        vser_: SerializerT
        kser_, vser_ = (
            cast("SerializerT[_KT]", self.resolver.primitive),
            cast("SerializerT[_VT]", self.resolver.primitive),
        )
        hascase = annotation.serde.flags.case is not None
        hasfilter = bool(annotation.serde.flags.omit)
        haskeyfilter = bool(annotation.serde.flags.exclude)

        args = cast("tuple[type[_KT], type[_VT]]", util.get_args(annotation.resolved))
        if args:
            kt, vt = args
            ktr = cast(
                "Annotation[_KT]",
                self.resolver.annotation(kt, flags=annotation.serde.flags),
            )
            vtr = cast(
                "Annotation[_VT]",
                self.resolver.annotation(vt, flags=annotation.serde.flags),
            )
            kser_, vser_ = (
                self.resolver.ser.factory(ktr),
                self.resolver.ser.factory(vtr),
            )

        if (hascase, hasfilter, haskeyfilter) == (True, True, True):
            case = annotation.serde.flags.case.transformer
            omit = annotation.serde.flags.omit
            exclude = annotation.serde.flags.exclude

            def case_keys_filters_dict_serializer(
                o: Mapping[str, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __case=case,
                __omit=tuple(omit),
                __exclude=frozenset(exclude),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
                return (
                    (
                        (case(__kser(k)), __vser(v))
                        for k, v in o.items()
                        if k not in __exclude and v not in __omit
                    )
                    if lazy
                    else {
                        case(__kser(k)): __vser(v)
                        for k, v in o.items()
                        if k not in __exclude and v not in __omit
                    }
                )

            return cast("SerializerT[_T]", case_keys_filters_dict_serializer)

        if (hascase, hasfilter, haskeyfilter) == (False, True, True):
            omit = annotation.serde.flags.omit
            exclude = annotation.serde.flags.exclude

            def keys_filters_dict_serializer(
                o: Mapping[_KT, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __omit=tuple(omit),
                __exclude=frozenset(exclude),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[PrimitiveT, PrimitiveT] | Iterator[tuple[PrimitiveT, PrimitiveT]]:
                return (
                    (
                        (__kser(k), __vser(v))
                        for k, v in o.items()
                        if k not in __exclude and v not in __omit
                    )
                    if lazy
                    else {
                        __kser(k): __vser(v)
                        for k, v in o.items()
                        if k not in __exclude and v not in __omit
                    }
                )

            return cast("SerializerT[_T]", keys_filters_dict_serializer)

        if (hascase, hasfilter, haskeyfilter) == (True, False, True):
            case = annotation.serde.flags.case.transformer
            exclude = annotation.serde.flags.exclude

            def case_keys_dict_serializer(
                o: Mapping[str, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __case=case,
                __exclude=frozenset(exclude),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
                return (
                    ((__case(__kser(k)), __vser(o[k])) for k in o.keys() - __exclude)
                    if lazy
                    else {__case(__kser(k)): __vser(o[k]) for k in o.keys() - __exclude}
                )

            return cast("SerializerT[_T]", case_keys_dict_serializer)

        if (hascase, hasfilter, haskeyfilter) == (True, True, False):
            case = annotation.serde.flags.case.transformer
            omit = annotation.serde.flags.omit

            def case_filters_dict_serializer(
                o: Mapping[str, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __case=case,
                __omit=tuple(omit),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
                return (
                    (
                        (__case(__kser(k)), __vser(v))
                        for k, v in o.items()
                        if v not in __omit
                    )
                    if lazy
                    else {
                        __case(__kser(k)): __vser(v)
                        for k, v in o.items()
                        if v not in __omit
                    }
                )

            return cast("SerializerT[_T]", case_filters_dict_serializer)

        if (hascase, hasfilter, haskeyfilter) == (True, False, False):
            case = annotation.serde.flags.case.transformer

            def case_serializer(
                o: Mapping[str, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __case=case,
                __kser=kser_,
                __vser=vser_,
            ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
                return (
                    ((__case(__kser(k)), __vser(v)) for k, v in o.items())
                    if lazy
                    else {__case(__kser(k)): __vser(v) for k, v in o.items()}
                )

            return cast("SerializerT[_T]", case_serializer)

        if (hascase, hasfilter, haskeyfilter) == (False, True, False):
            omit = annotation.serde.flags.omit

            def filters_dict_serializer(
                o: Mapping[_KT, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __omit=tuple(omit),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[PrimitiveT, PrimitiveT] | Iterator[tuple[PrimitiveT, PrimitiveT]]:
                return (
                    ((__kser(k), __vser(v)) for k, v in o.items() if v not in __omit)
                    if lazy
                    else {__kser(k): __vser(v) for k, v in o.items() if v not in __omit}
                )

            return cast("SerializerT[_T]", filters_dict_serializer)

        if (hascase, hasfilter, haskeyfilter) == (False, False, True):
            exclude = annotation.serde.flags.exclude

            def keys_dict_serializer(
                o: Mapping[_KT, _VT],
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __exclude=frozenset(exclude),
                __kser=kser_,
                __vser=vser_,
            ) -> dict[PrimitiveT, PrimitiveT] | Iterator[tuple[PrimitiveT, PrimitiveT]]:
                return (
                    ((__kser(k), __vser(o[k])) for k in o.keys() - __exclude)
                    if lazy
                    else {__kser(k): __vser(o[k]) for k in o.keys() - __exclude}
                )

            return cast("SerializerT[_T]", keys_dict_serializer)

        def dict_serializer(
            o: Mapping,
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __kser=kser_,
            __vser=vser_,
        ) -> dict[PrimitiveT, PrimitiveT] | Iterator[tuple[PrimitiveT, PrimitiveT]]:
            return (
                ((__kser(k), __vser(o[k])) for k, v in o.items())
                if lazy
                else {__kser(k): __vser(o[k]) for k, v in o.items()}
            )

        return cast("SerializerT[_T]", dict_serializer)


class FieldsRoutine(BaseRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        annotation = self.annotation
        fields_ser = {
            x: self.resolver.ser.factory(y) for x, y in annotation.serde.fields.items()
        }
        iterator = self.resolver.translator.iterator(
            annotation.resolved,
            relaxed=True,
            # We want to proactively exclude defined fields from this iterator.
            exclude=(*annotation.serde.flags.exclude,),
            only=frozenset(annotation.serde.fields_out.keys()),
            omit=(*(annotation.serde.flags.omit or ()),),
        )
        transforms = {f: t for f, t in annotation.serde.fields_out.items() if f != t}
        if transforms:

            def field_transforms_serializer(
                o: _T,
                *,
                name: util.ReprT = None,
                lazy: bool = False,
                __fields_ser=MappingProxyType(fields_ser),
                __transforms=MappingProxyType(transforms),
            ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
                return (
                    (
                        (__transforms.get(f, f), __fields_ser[f](v))
                        for f, v in iterator(o)
                    )
                    if lazy
                    else {
                        __transforms.get(f, f): __fields_ser[f](v)
                        for f, v in iterator(o)
                    }
                )

            return cast("SerializerT[_T]", field_transforms_serializer)

        def field_serializer(
            o: _T,
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __fields_ser=MappingProxyType(fields_ser),
        ) -> dict[str, PrimitiveT] | Iterator[tuple[str, PrimitiveT]]:
            return (
                ((f, __fields_ser[f](v)) for f, v in iterator(o))
                if lazy
                else {f: __fields_ser[f](v) for f, v in iterator(o)}
            )

        return cast("SerializerT[_T]", field_serializer)


class FixedTupleRoutine(BaseRoutine[Tuple[_VT]]):
    def _get_serializer(self) -> SerializerT[_T]:
        annotation = self.annotation
        fields_ser = {
            ix: self.resolver.ser.factory(self.resolver.annotation(y))
            for ix, y in enumerate(annotation.args)
        }

        def fixed_tuple_serializer(
            o: Tuple[_VT],
            *,
            name: util.ReprT = None,
            lazy: bool = False,
            __fields_ser=MappingProxyType(fields_ser),
        ) -> list[PrimitiveT] | Iterator[PrimitiveT]:
            return (
                (__fields_ser[i](v) for i, v in enumerate(o) if i in __fields_ser)
                if lazy
                else [__fields_ser[i](v) for i, v in enumerate(o) if i in __fields_ser]
            )

        return cast("SerializerT[_T]", fixed_tuple_serializer)


class EnumRoutine(BaseRoutine[_T]):
    def _get_serializer(self) -> SerializerT[_T]:
        annotation = self.annotation
        origin: type[enum.Enum] = cast("type[enum.Enum]", annotation.resolved_origin)
        ts = {type(x.value) for x in origin}
        if len(ts) > 1:
            return cast("SerializerT[_T]", self.resolver.primitive)
        # If we can predict a single type then return the serializer for that
        t = ts.pop()
        va = self.resolver.annotation(
            t,
            flags=annotation.serde.flags,
            is_optional=annotation.optional,
            is_strict=annotation.strict,
            parameter=annotation.parameter,
            default=annotation.parameter.default,
        )
        vser = self.resolver.ser.factory(va)

        if va.optional:

            def optional_enum_serializer(
                o: enum.Enum | None,
                *,
                lazy: bool = False,
                name: util.ReprT = None,
                _vser=vser,
            ) -> PrimitiveT | None:
                if o is None:
                    return o
                return _vser(o.value, lazy=lazy, name=name)

            return cast("SerializerT[_T]", optional_enum_serializer)

        def enum_serializer(
            o: enum.Enum,
            *,
            lazy: bool = False,
            name: util.ReprT = None,
            _vser=vser,
        ) -> PrimitiveT:
            return _vser(o.value, lazy=lazy, name=name)

        return cast("SerializerT[_T]", enum_serializer)


class SerializationValueError(ValueError):
    ...


_decode = operator.methodcaller("decode", common.DEFAULT_ENCODING)
_pattern = operator.attrgetter("pattern")
_secret = operator.attrgetter("secret")
_CheckT = Callable[[Any, util.ReprT], TypeGuard[PrimitiveT]]
