import datetime
import inspect
import re
from collections import deque
from operator import attrgetter
from typing import (
    Mapping,
    Any,
    Union,
    Callable,
    Type,
    Dict,
    Collection,
    Tuple,
    List,
    Pattern,
    Match,
    cast,
    TYPE_CHECKING,
    Optional,
)

from pendulum import parse as dateparse

from typic import checks, gen, constraints as const
from typic.strict import STRICT_MODE
from typic.util import safe_eval, hexhash, origin as get_origin, cached_issubclass
from typic.common import DEFAULT_ENCODING, VAR_POSITIONAL, VAR_KEYWORD, ObjectT
from .common import DeserializerT, DeserializerRegistryT, SerdeConfig, Annotation

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver

_ORIG_SETTER_NAME = "__setattr_original__"
_origsettergetter = attrgetter(_ORIG_SETTER_NAME)
_TYPIC_ANNOS_NAME = "__typic_annotations__"
_annosgetter = attrgetter(_TYPIC_ANNOS_NAME)
_TOO_MANY_POS = "too many positional arguments"
_VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
_VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD
_KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
_POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
_POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
_KWD_KINDS = {_VAR_KEYWORD, _KEYWORD_ONLY}
_POS_KINDS = {_VAR_POSITIONAL, _POSITIONAL_ONLY}
_empty = inspect.Signature.empty
_RETURN_KEY = "return"
_SELF_NAME = "self"
_TO_RESOLVE: List[Union[Type, Callable]] = []
_SCHEMA_NAME = "__json_schema__"


class DesFactory:
    """A callable class for ``des``erialzing values.

    Checks for:

            - builtin types
            - :py:mod:`typing` type annotations
            - :py:class:`datetime.date`
            - :py:class:`datetime.datetime`
            - :py:class:`typing.TypedDict`
            - :py:class:`typing.NamedTuple`
            - :py:func:`collections.namedtuple`
            - User-defined classes (limited)

    Examples
    --------
    >>> import typic
    >>> typic.transmute(bytes, "foo")
    b'foo'
    >>> typic.transmute(dict, "{'foo': 'bar'}")
    {'foo': 'bar'}
    """

    STRICT = STRICT_MODE
    DEFAULT_BYTE_ENCODING = "utf-8"
    UNRESOLVABLE = frozenset(
        (
            Any,
            Union,
            Match,
            re.Match,  # type: ignore
            type(None),
            _empty,
        )
    )
    VNAME = "val"
    VTYPE = "vtype"
    __DES_CACHE: Dict[str, Tuple[DeserializerT, "const.ValidatorT"]] = {}
    __USER_DESS: DeserializerRegistryT = deque()

    def __init__(self, resolver: "Resolver"):
        self.resolver = resolver
        for typ in checks.BUILTIN_TYPES:
            self.factory(self.resolver.annotation(typ))

    def register(self, deserializer: DeserializerT, check: DeserializerT):
        """Register a user-defined coercer.

        In the rare case where typic can't figure out how to coerce your annotation
        correctly, a custom coercer may be registered alongside a check function which
        returns a simple boolean indicating whether this is the correct coercer for an
        annotation.
        """
        self.__USER_DESS.appendleft((check, deserializer))

    def _set_checks(self, func: gen.Block, annotation: "Annotation"):
        _checks = []
        _ctx = {}
        if annotation.optional:
            _checks.append(f"{self.VNAME} is None")
        if annotation.has_default:
            _checks.append(f"{self.VNAME} == __default")
            _ctx["__default"] = annotation.parameter.default
        if _checks:
            check = " or ".join(_checks)
            func.l(f"if {check}:", **_ctx)
            with func.b() as b:
                b.l(f"return {self.VNAME}")

    @staticmethod
    def _get_des_name(annotation: "Annotation") -> str:
        return f"deserializer_{hexhash(annotation)}"

    def _build_date_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        origin = get_origin(annotation.resolved)
        if issubclass(origin, datetime.datetime):
            with func.b(f"if issubclass({self.VTYPE}, datetime.date):") as b:
                b.l(
                    f"{self.VNAME} = "
                    f"{anno_name}("
                    f"{self.VNAME}.year, "
                    f"{self.VNAME}.month, "
                    f"{self.VNAME}.day)",
                    datetime=datetime,
                )
        elif issubclass(origin, datetime.date):
            with func.b(f"if issubclass({self.VTYPE}, datetime.datetime):") as b:
                b.l(f"{self.VNAME} = {self.VNAME}.date()", datetime=datetime)
        with func.b(f"elif issubclass({self.VTYPE}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}.fromtimestamp({self.VNAME})")
        with func.b(f"elif issubclass({self.VTYPE}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME})"
            # We do the negative assertion here because all datetime objects are
            # subclasses of date.
            if not issubclass(origin, datetime.datetime):
                line = f"{line}.date()"
            b.l(line, dateparse=dateparse)

    def _add_eval(self, func: gen.Block):
        func.l(
            f"_, {self.VNAME} = __eval({self.VNAME}) "
            f"if issubclass({self.VTYPE}, (str, bytes)) "
            f"else (False, {self.VNAME})",
            __eval=safe_eval,
        )
        func.l(f"{self.VTYPE} = type({self.VNAME})")

    def _add_subclass_check(self, func: gen.Block, anno_name: str):
        with func.b(f"if issubclass({self.VTYPE}, {anno_name}):") as b:
            b.l(f"{gen.Keyword.RET} {self.VNAME}")

    def _build_builtin_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation",
    ):
        origin = get_origin(annotation.resolved)
        # We should try and evaluate inputs for anything that isn't a subclass of str.
        if issubclass(origin, (Collection, bool, int)) and not issubclass(
            origin, (str, bytes)
        ):
            self._add_eval(func)
        # Encode for bytes
        if issubclass(origin, bytes):
            with func.b(f"if issubclass({self.VTYPE}, str):") as b:
                b.l(
                    f"{self.VNAME} = {anno_name}("
                    f"{self.VNAME}, encoding={DEFAULT_ENCODING!r})"
                )
        # Decode for str
        elif issubclass(origin, str):
            with func.b(f"if issubclass({self.VTYPE}, (bytes, bytearray)):") as b:
                b.l(f"{self.VNAME} = {self.VNAME}.decode({DEFAULT_ENCODING!r})")
        # Translate fields for a mapping
        if issubclass(origin, Mapping) and annotation.serde.fields_in:
            line = f"{anno_name}({{fields_in[x]: y for x, y in {self.VNAME}.items()}})"
        # Coerce to the target type.
        else:
            line = f"{anno_name}({self.VNAME})"
        func.l(f"{self.VNAME} = {line}")

    def _build_pattern_des(self, func: gen.Block, anno_name: str):
        func.l(
            f"{self.VNAME} = {self.VNAME} "
            f"if issubclass({self.VTYPE}, {anno_name}) "
            f"else __re_compile({self.VNAME})",
            __re_compile=re.compile,
        )

    def _build_fromdict_des(self, func: gen.Block, anno_name: str):
        self._add_subclass_check(func, anno_name)
        self._add_eval(func)
        func.l(f"{self.VNAME} = {anno_name}.from_dict({self.VNAME})")

    def _build_typeddict_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        *,
        total: bool = True,
        eval: bool = True,
    ):
        if eval:
            self._add_eval(func)

        fields_deser = {
            x: self.resolver.resolve(
                y.resolved,
                flags=y.serde.flags,
                name=x,
                parameter=y.parameter,
                is_optional=y.optional,
                is_strict=y.strict,
            ).transmute
            for x, y in annotation.serde.fields.items()
        }
        x = "fields_in[x]"
        y = f"fields_deser[x]({self.VNAME}[x])" if fields_deser else f"{self.VNAME}[x]"
        line = f"{{{x}: {y} for x in fields_in.keys()"
        tail = "}" if total else f"& {self.VNAME}.keys()}}"
        func.l(f"{self.VNAME} = {anno_name}(**{line}{tail})", fields_deser=fields_deser)

    def _build_typedtuple_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        self._add_eval(func)
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=Mapping) as b:
            if annotation.serde.fields:
                self._build_typeddict_des(b, anno_name, annotation, eval=False)
            else:
                b.l(f"{self.VNAME} = {anno_name}(**{self.VNAME})",)
        with func.b(
            f"elif issubclass({self.VTYPE}, (list, set, frozenset, tuple)):"
        ) as b:
            if annotation.serde.fields:
                b.l(
                    f"{self.VNAME} = __bind({anno_name}, *{self.VNAME}).eval()",
                    __bind=self.resolver.bind,
                )
            else:
                b.l(f"{self.VNAME} = {anno_name}(*{self.VNAME})",)

    def _build_mapping_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation",
    ):
        key_des, item_des = None, None
        args = annotation.args
        if args:
            args = cast(Tuple[Type, Type], args)
            key_type, item_type = args
            key_des = self.resolver.resolve(key_type, flags=annotation.serde.flags)
            item_des = self.resolver.resolve(item_type, flags=annotation.serde.flags)
        kd_name = f"{anno_name}_key_des"
        it_name = f"{anno_name}_item_des"
        line = f"{anno_name}({self.VNAME})"
        if args or annotation.serde.fields_in:
            x, y = "x", "y"
            # If there are args & field mapping, get the correct field name
            # AND serialize the key.
            if args and annotation.serde.fields_in:
                x = f"{kd_name}(fields_in.get(x, x))"
            # If there is only a field mapping, get the correct name for the field.
            elif annotation.serde.fields_in:
                x = f"fields_in.get(x, x)"
            # If there are only serializers, get the serialized value
            elif args:
                x = f"{kd_name}(x)"
                y = f"{it_name}(y)"
            # Write the line.
            line = f"{anno_name}({{{x}: {y} for x, y in {self.VNAME}.items()}})"
        self._add_eval(func)
        func.l(
            f"{self.VNAME} = {line}",
            level=None,
            **{kd_name: key_des, it_name: item_des},
        )

    def _build_collection_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        item_des = None
        it_name = f"{anno_name}_item_des"
        line = f"{self.VNAME} = {anno_name}({self.VNAME})"
        if annotation.args:
            item_type = annotation.args[0]
            item_des = self.resolver.resolve(item_type, flags=annotation.serde.flags)
            line = (
                f"{self.VNAME} = "
                f"{anno_name}({it_name}(x) for x in {anno_name}({self.VNAME}))"
            )

        self._add_eval(func)
        func.l(line, level=None, **{it_name: item_des})

    def _build_generic_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        self._add_subclass_check(func, anno_name)
        self._add_eval(func)
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=Mapping) as b:
            if annotation.serde.fields_in != annotation.serde.fields_out:
                x = "fields_in[x]"
                y = f"{self.VNAME}[x]"
                b.l(
                    f"{self.VNAME} = "
                    f"{{{x}: {y} for x in fields_in.keys() & {self.VNAME}.keys()}}"
                )
            if not self.resolver.seen(annotation.resolved):
                b.l(
                    f"bound = __bind({anno_name}, **{self.VNAME})",
                    __bind=self.resolver.bind,
                )
                b.l(f"{self.VNAME} = bound.eval()")
            else:
                b.l(f"{self.VNAME} = {anno_name}(**{self.VNAME})")
        with func.b("else:") as b:
            b.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_des(self, annotation: "Annotation",) -> Callable:
        func_name = self._get_des_name(annotation)
        args = annotation.args
        # Get the "origin" of the annotation.
        # For natives and their typing.* equivs, this will be a builtin type.
        # For SpecialForms (Union, mainly) this will be the un-subscripted type.
        # For custom types or classes, this will be the same as the annotation.
        anno_name = f"{func_name}_anno"
        origin = get_origin(annotation.resolved)
        ns = {
            anno_name: origin,
            "issubclass": cached_issubclass,
            **annotation.serde.asdict(),
        }
        with gen.Block(ns) as main:
            with main.f(func_name, main.param(f"{self.VNAME}")) as func:
                func.l(f"{self.VTYPE} = type({self.VNAME})")
                if origin not in self.UNRESOLVABLE:
                    self._set_checks(func, annotation)
                    if checks.isdatetype(origin):
                        self._build_date_des(func, anno_name, annotation)
                    elif origin in {Pattern, re.Pattern}:  # type: ignore
                        self._build_pattern_des(func, anno_name)
                    elif not args and checks.isbuiltintype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.isfromdictclass(origin):
                        self._build_fromdict_des(func, anno_name)
                    elif checks.isenumtype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.istypeddict(origin):
                        self._build_typeddict_des(
                            func, anno_name, annotation, total=origin.__total__
                        )
                    elif checks.istypedtuple(origin) or checks.isnamedtuple(origin):
                        self._build_typedtuple_des(func, anno_name, annotation)
                    elif not args and checks.isbuiltinsubtype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.ismappingtype(origin):
                        self._build_mapping_des(func, anno_name, annotation)
                    elif checks.iscollectiontype(origin):
                        self._build_collection_des(func, anno_name, annotation)
                    else:
                        self._build_generic_des(func, anno_name, annotation)
                func.l(f"{gen.Keyword.RET} {self.VNAME}")
        deserializer = main.compile(ns=ns, name=func_name)
        self.__DES_CACHE[func_name] = deserializer
        return deserializer

    def _check_varargs(self, anno: "Annotation", des: DeserializerT,) -> DeserializerT:
        if anno.parameter.kind == VAR_POSITIONAL:
            __des = des

            def des(__val, *, __des=__des):
                return (*(__des(x) for x in __val),)

        elif anno.parameter.kind == VAR_KEYWORD:
            __des = des

            def des(__val, *, __des=__des):
                return {x: __des(y) for x, y in __val.items()}

        return des

    def _finalize_validator(
        self, des: DeserializerT, constr: Optional["const.ConstraintsT"],
    ) -> "const.ValidatorT":
        def validate(o):
            return o

        if constr:
            validate = constr.validate  # noqa: F811

        # Special case for type-constraints which should be coerced for validation.
        if isinstance(constr, const.TypeConstraints) and constr.coerce:
            validate = des
        return validate

    def _finalize_deserializer(
        self,
        anno: "Annotation",
        des: DeserializerT,
        constr: Optional["const.ConstraintsT"],
    ) -> Tuple[DeserializerT, "const.ValidatorT"]:
        # Handle *args and **kwargs
        des = self._check_varargs(anno, des)
        # Determine how to run in "strict-mode"
        validator = self._finalize_validator(des, constr)
        # If we have type constraints, only validate if we're in strict mode.
        if isinstance(constr, const.TypeConstraints):
            if anno.strict:
                des = validator
        # Otherwise
        else:
            # In strict mode, we validate & coerce if there are constraints
            if anno.strict and constr and constr.coerce:
                __d = des

                def des(val: Any, *, __d=__d, __v=validator) -> ObjectT:
                    return __d(__v(val))

            elif anno.strict:
                des = validator

        return des, validator

    def factory(
        self, annotation: "Annotation", constr: Optional["const.ConstraintsT"] = None
    ) -> Tuple[DeserializerT, "const.ValidatorT"]:
        annotation.serde = annotation.serde or SerdeConfig()
        key = self._get_des_name(annotation)
        if key in self.__DES_CACHE:
            return self.__DES_CACHE[key]
        deserializer: Optional[DeserializerT] = None
        for check, des in self.__USER_DESS:
            if check(annotation.resolved):
                deserializer = des
                break
        if not deserializer:
            deserializer = self._build_des(annotation)

        deserializer, validator = self._finalize_deserializer(
            annotation, deserializer, constr
        )
        self.__DES_CACHE[key] = (deserializer, validator)

        return deserializer, validator
