import datetime
import functools
import inspect
import pathlib
import re
import uuid
from collections import deque, defaultdict, abc
from operator import attrgetter
from typing import (
    Mapping,
    Any,
    Union,
    Callable,
    Type,
    Dict,
    Tuple,
    List,
    Pattern,
    Match,
    cast,
    TYPE_CHECKING,
    Optional,
    Set,
)

from pendulum import parse as dateparse, DateTime, instance

from typic import checks, gen, constraints as const
from typic.strict import STRICT_MODE
from typic.util import (
    safe_eval,
    cached_issubclass,
    cached_signature,
    get_defname,
    get_tag_for_types,
    get_unique_name,
)
from typic.common import DEFAULT_ENCODING, VAR_POSITIONAL, VAR_KEYWORD, ObjectT
from .common import (
    DeserializerT,
    DeserializerRegistryT,
    SerdeConfig,
    Annotation,
    DelayedAnnotation,
    ForwardDelayedAnnotation,
    AnnotationT,
)

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

    def register(self, deserializer: DeserializerT, check: DeserializerT):
        """Register a user-defined coercer.

        In the rare case where typic can't figure out how to coerce your annotation
        correctly, a custom coercer may be registered alongside a check function which
        returns a simple boolean indicating whether this is the correct coercer for an
        annotation.
        """
        self.__USER_DESS.appendleft((check, deserializer))

    def _set_checks(self, func: gen.Block, anno_name: str, annotation: "Annotation"):
        _ctx = {}
        # run a safe eval if input is text and anno isn't
        if inspect.isclass(annotation.resolved_origin) and issubclass(
            annotation.resolved_origin, (str, bytes)
        ):
            self._add_vtype(func)
        else:
            self._add_eval(func)
        # Equality checks for defaults and optionals
        custom_equality = hasattr(annotation.resolved_origin, "equals")
        if custom_equality and (annotation.optional or annotation.has_default):
            func.l(f"custom_equality = hasattr({self.VNAME}, 'equals')")
        null = ""
        if annotation.optional:
            null = f"{self.VNAME} in {self.resolver.OPTIONALS}"
            if custom_equality:
                null = (
                    f"(any({self.VNAME}.equals(o) for o in {self.resolver.OPTIONALS}) "
                    "if custom_equality "
                    f"else {null})"
                )
        eq = ""
        if (
            annotation.has_default
            and annotation.parameter.default not in self.resolver.OPTIONALS
        ):
            eq = f"{self.VNAME} == __default"
            if custom_equality:
                if hasattr(annotation.parameter.default, "equals"):
                    eq = f"__default.equals({self.VNAME})"
                eq = f"{self.VNAME}.equals(__default) if custom_equality else {eq}"
            _ctx["__default"] = annotation.parameter.default
        if eq or null:
            # Add a type-check for anything that isn't a builtin.
            if eq and not checks.isbuiltintype(annotation.resolved_origin):
                eq = f"{self.VTYPE} is {anno_name} and {eq}"
            check = " or ".join(c for c in (null, eq) if c)
            with func.b(f"if {check}:", **_ctx) as b:  # type: ignore
                b.l(f"return {self.VNAME}")

    @staticmethod
    def _get_name(
        annotation: "Annotation", constr: Optional["const.ConstraintsT"]
    ) -> str:
        return get_defname("deserializer", (annotation, constr))

    def _build_date_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        origin = annotation.resolved_origin
        if issubclass(origin, datetime.datetime):
            with func.b(
                f"if isinstance({self.VNAME}, datetime):", datetime=datetime.datetime
            ) as b:
                # Use pendulum's helper if possible.
                if origin is DateTime:
                    b.l(f"{self.VNAME} = instance({self.VNAME})", instance=instance)
                else:
                    b.l(
                        f"{self.VNAME} = "
                        f"{anno_name}("
                        f"{self.VNAME}.year, "
                        f"{self.VNAME}.month, "
                        f"{self.VNAME}.day, "
                        f"{self.VNAME}.hour, "
                        f"{self.VNAME}.minute, "
                        f"{self.VNAME}.second, "
                        f"{self.VNAME}.microsecond, "
                        f"{self.VNAME}.tzinfo"
                        f")",
                    )
            with func.b(
                f"elif isinstance({self.VNAME}, date):", date=datetime.date
            ) as b:
                b.l(
                    f"{self.VNAME} = "
                    f"{anno_name}("
                    f"{self.VNAME}.year, "
                    f"{self.VNAME}.month, "
                    f"{self.VNAME}.day"
                    f")",
                )
        elif issubclass(origin, datetime.date):
            with func.b(
                f"if isinstance({self.VNAME}, datetime):", datetime=datetime.datetime
            ) as b:
                b.l(f"{self.VNAME} = {self.VNAME}.date()")
        with func.b(f"elif isinstance({self.VNAME}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}.fromtimestamp({self.VNAME})")
        with func.b(f"elif isinstance({self.VNAME}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME})"
            # We do the negative assertion here because all datetime objects are
            # subclasses of date.
            if not issubclass(origin, datetime.datetime):
                line = f"{line}.date()"
            b.l(line, dateparse=dateparse)

    def _build_uuid_des(
        self, func: gen.Block, anno_name: str, annotation: "Annotation"
    ):
        self._add_type_check(func, anno_name)
        with func.b(f"if issubclass({self.VTYPE}, UUID):", UUID=uuid.UUID) as b:
            b.l(f"{self.VNAME} = {anno_name}(int={self.VNAME}.int)")

        with func.b(f"elif isinstance({self.VNAME}, str):") as b:
            b.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, bytes):") as b:
            b.l(f"{self.VNAME} = {anno_name}(bytes={self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, int):") as b:
            b.l(f"{self.VNAME} = {anno_name}(int={self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, tuple):") as b:
            b.l(f"{self.VNAME} = {anno_name}(fields={self.VNAME})")

    def _add_eval(self, func: gen.Block):
        func.l(
            f"_, {self.VNAME} = __eval({self.VNAME}) "
            f"if isinstance({self.VNAME}, (str, bytes)) "
            f"else (False, {self.VNAME})",
            __eval=safe_eval,
        )
        self._add_vtype(func)

    def _add_type_check(self, func: gen.Block, anno_name: str):
        with func.b(f"if {self.VTYPE} is {anno_name}:") as b:
            b.l(f"{gen.Keyword.RET} {self.VNAME}")

    def _add_vtype(self, func: gen.Block):
        func.l(f"{self.VTYPE} = {self.VNAME}.__class__")

    def _get_default_factory(self, annotation: "AnnotationT"):
        factory: Union[Type, Callable[..., Any], None] = None
        args: Tuple = annotation.args if isinstance(annotation, Annotation) else tuple()
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
                factory_nested = self._get_default_factory(factory_anno)

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

    def _build_text_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
    ):
        origin = annotation.resolved_origin
        # Encode for bytes
        if issubclass(origin, bytes):
            with func.b(f"if isinstance({self.VNAME}, str):") as b:
                b.l(
                    f"{self.VNAME} = {anno_name}("
                    f"{self.VNAME}, encoding={DEFAULT_ENCODING!r})"
                )
        # Decode for str
        elif issubclass(origin, str):
            with func.b(f"if isinstance({self.VNAME}, (bytes, bytearray)):") as b:
                b.l(f"{self.VNAME} = {self.VNAME}.decode({DEFAULT_ENCODING!r})")
        func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_builtin_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
    ):
        origin = annotation.resolved_origin
        if issubclass(origin, (str, bytes)):
            self._build_text_des(func, anno_name, annotation)
        elif checks.ismappingtype(origin):
            self._build_mapping_des(func, anno_name, annotation)
        elif checks.iscollectiontype(origin):
            self._build_collection_des(func, anno_name, annotation)
        # bool, int, float...
        else:
            func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_pattern_des(self, func: gen.Block, anno_name: str):
        func.l(
            f"{self.VNAME} = {self.VNAME} "
            f"if issubclass({self.VTYPE}, {anno_name}) "
            f"else __re_compile({self.VNAME})",
            __re_compile=re.compile,
        )

    def _build_fromdict_des(self, func: gen.Block, anno_name: str):
        self._add_type_check(func, anno_name)
        func.l(f"{self.VNAME} = {anno_name}.from_dict({self.VNAME})")

    def _build_typeddict_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        *,
        total: bool = True,
        namespace: Type = None,
    ):

        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            fields_deser = {
                x: self.resolver._resolve_from_annotation(
                    y, _namespace=namespace
                ).transmute
                for x, y in annotation.serde.fields.items()
            }
            x = "fields_in[x]"
            y = (
                f"fields_deser[x]({self.VNAME}[x])"
                if fields_deser
                else f"{self.VNAME}[x]"
            )
            line = f"{{{x}: {y} for x in fields_in.keys()"
            tail = "}" if total else f"& {self.VNAME}.keys()}}"
            b.l(
                f"{self.VNAME} = {anno_name}(**{line}{tail})", fields_deser=fields_deser
            )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_typedtuple_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        namespace: Type = None,
    ):
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            if annotation.serde.fields:
                self._build_typeddict_des(b, anno_name, annotation, namespace=namespace)
            else:
                b.l(
                    f"{self.VNAME} = {anno_name}(**{self.VNAME})",
                )
        with func.b(
            f"elif isinstance({self.VNAME}, (list, set, frozenset, tuple)):"
        ) as b:
            if annotation.serde.fields:
                b.l(
                    f"{self.VNAME} = __bind({anno_name}, *{self.VNAME}).eval()",
                    __bind=self.resolver.bind,
                )
            else:
                b.l(
                    f"{self.VNAME} = {anno_name}(*{self.VNAME})",
                )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_mapping_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        namespace: Type = None,
    ):
        key_des, item_des = None, None
        args = annotation.args
        if args:
            args = cast(Tuple[Type, Type], args)
            key_type, item_type = args
            key_des = self.resolver.resolve(
                key_type, flags=annotation.serde.flags, namespace=namespace
            )
            item_des = self.resolver.resolve(
                item_type, flags=annotation.serde.flags, namespace=namespace
            )
        if issubclass(annotation.resolved_origin, defaultdict):
            factory = self._get_default_factory(annotation)
            func.namespace[anno_name] = functools.partial(defaultdict, factory)
        kd_name = f"{anno_name}_key_des"
        it_name = f"{anno_name}_item_des"
        iterate = f"iterate({self.VNAME})"
        line = f"{anno_name}({iterate})"
        if args or annotation.serde.fields_in:
            x, y = "x", "y"
            # If there are args & field mapping, get the correct field name
            # AND serialize the key.
            if args and annotation.serde.fields_in:
                x = f"{kd_name}(fields_in.get(x, x))"
            # If there is only a field mapping, get the correct name for the field.
            elif annotation.serde.fields_in:
                x = "fields_in.get(x, x)"
            # If there are only serializers, get the serialized value
            elif args:
                x = f"{kd_name}(x)"
                y = f"{it_name}(y)"
            line = f"{anno_name}({{{x}: {y} for x, y in {iterate}}})"
        # If we don't have nested annotations, we can short-circuit on valid inputs
        else:
            self._add_type_check(func, anno_name)
        # Write the lines.
        func.l(
            f"{self.VNAME} = {line}",
            level=None,
            **{
                kd_name: key_des,
                it_name: item_des,
                "Mapping": abc.Mapping,
                "iterate": self.resolver.iterate,
            },
        )

    def _build_collection_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        namespace: Type = None,
    ):
        item_des = None
        it_name = f"{anno_name}_item_des"
        iterate = f"iterate({self.VNAME}, values=True)"
        line = f"{self.VNAME} = {anno_name}({iterate})"
        if annotation.args:
            item_type = annotation.args[0]
            item_des = self.resolver.resolve(
                item_type, flags=annotation.serde.flags, namespace=namespace
            )
            line = (
                f"{self.VNAME} = "
                f"{anno_name}({it_name}(x) for x in parent({iterate}))"
            )
        else:
            self._add_type_check(func, anno_name)
        func.l(
            line,
            level=None,
            **{
                it_name: item_des,
                "Collection": abc.Collection,
                "iterate": self.resolver.iterate,
            },
        )

    def _build_path_des(self, func: gen.Block, anno_name: str):
        self._add_type_check(func, anno_name)
        func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_generic_des(
        self,
        func: gen.Block,
        anno_name: str,
        annotation: "Annotation",
        namespace: Type = None,
    ):
        serde = annotation.serde
        resolved = annotation.resolved
        self._add_type_check(func, anno_name)
        # Main branch - we have a mapping for a user-defined class.
        # This is where the serde configuration comes in.
        # WINDY PATH AHEAD
        func.l("# Happy path - deserialize a mapping into the object.")
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            # Universal line - transform input to known keys/values.
            # Specific values may change.
            def mainline(k, v):
                return f"{{{k}: {v} for x in fields_in.keys() & {self.VNAME}.keys()}}"

            # The "happy path" - e.g., no guesswork needed.
            def happypath(k, v, **ns):
                b.l(f"{self.VNAME} = {anno_name}(**{mainline(k, v)})", **ns)

            # Default X - translate given `x` to known input `x`
            x = "fields_in[x]"
            # No field name translation needs to happen.
            if {*serde.fields_in.keys()} == {*serde.fields_in.values()}:
                x = "x"

            # Default Y - get the given `y` with the given `x`
            y = f"{self.VNAME}[x]"
            # Get the intersection of known input fields and annotations.
            matched = {*serde.fields_in.values()} & serde.fields.keys()
            # Happy path! This is a `@typic.al` wrapped class.
            if self.resolver.known(resolved) or self.resolver.delayed(resolved):
                happypath(x, y)
            # Secondary happy path! We know how to deserialize already.
            else:
                fields_in = serde.fields_in
                if serde.fields and len(matched) == len(serde.fields_in):
                    desers = {
                        f: self.resolver._resolve_from_annotation(
                            serde.fields[f], _namespace=namespace
                        ).transmute
                        for f in matched
                    }
                else:
                    protocols = self.resolver.protocols(annotation.resolved_origin)
                    fields_in = {x: x for x in protocols}
                    desers = {f: p.transmute for f, p in protocols.items()}
                y = f"desers[{x}]({self.VNAME}[x])"
                happypath(x, y, desers=desers, fields_in=fields_in)

        # Secondary branch - we have some other input for a user-defined class
        func.l("# Unknown path, just try casting it directly.")
        with func.b(
            f"elif isbuiltinsubtype({self.VTYPE}):",
            isbuiltinsubtype=checks.isbuiltinsubtype,
        ) as b:
            b.l(f"{self.VNAME} = {anno_name}({self.VNAME})")
        # Final branch - user-defined class for another user-defined class
        func.l(
            "# Two user-defined types, "
            "try to translate the input into the desired output."
        )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_literal_des(
        self, annotation: "Annotation", func_name: str, namespace: Type = None
    ):
        args = annotation.args
        types: Set[Type] = {a.__class__ for a in args}
        t = types.pop() if len(types) == 1 else Union[tuple(types)]
        t_anno = cast(
            Annotation,
            self.resolver.annotation(
                t,  # type: ignore
                name=annotation.parameter.name,
                # parameter=annotation.parameter,
                is_optional=annotation.optional,
                is_strict=annotation.strict,
                flags=annotation.serde.flags,
                default=annotation.parameter.default,
            ),
        )
        return self._build_des(t_anno, func_name, namespace)

    def _build_union_des(self, func: gen.Block, annotation: "Annotation", namespace):
        # Get all types which we may coerce to.
        args = (*(a for a in annotation.args if a not in {None, Ellipsis, type(None)}),)
        # Get all custom types, which may have discriminators
        targets = (*(a for a in args if not checks.isstdlibtype(a)),)
        # We can only build a tagged union deserializer if all args are valid
        if args and args == targets:
            # Try to collect the field which will be the discriminator.
            # First, get a mapping of Type -> Proto & Type -> Fields
            tagged = get_tag_for_types(targets)
            # Just bail out if we can't find a key.
            if not tagged:
                func.l("# No-op, couldn't locate a discriminator key.")
                return
            # If we got a key, re-map the protocols to the value for each type.
            deserializers = {
                value: self.resolver.resolve(t, namespace=namespace)
                for value, t in tagged.types_by_values
            }
            # Finally, build the deserializer
            func.namespace.update(
                tag=tagged.tag,
                desers=deserializers,
                empty=_empty,
            )
            with func.b(
                f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping
            ) as b:
                b.l(f"tag_value = {self.VNAME}.get(tag, empty)")
            with func.b("else:") as b:
                b.l(f"tag_value = getattr({self.VNAME}, tag, empty)")
            with func.b("if tag_value in desers:") as b:
                b.l(f"{self.VNAME} = desers[tag_value].transmute({self.VNAME})")
            with func.b("else:") as b:
                b.l(
                    "raise ValueError("
                    'f"Value is missing field {tag!r} with one of '
                    '{(*desers,)}: {val!r}"'
                    ")"
                )

    def _build_des(
        self, annotation: "Annotation", func_name: str, namespace: Type = None
    ) -> Callable:
        args = annotation.args
        # Get the "origin" of the annotation.
        # For natives and their typing.* equivs, this will be a builtin type.
        # For SpecialForms (Union, mainly) this will be the un-subscripted type.
        # For custom types or classes, this will be the same as the annotation.
        origin = annotation.resolved_origin
        anno_name = get_unique_name(origin)
        ns = {
            anno_name: origin,
            "parent": getattr(origin, "__parent__", origin),
            "issubclass": cached_issubclass,
            **annotation.serde.asdict(),
        }
        if checks.isliteral(origin):
            return self._build_literal_des(annotation, func_name, namespace)
        with gen.Block(ns) as main:
            with main.f(func_name, main.param(f"{self.VNAME}")) as func:
                if origin not in self.UNRESOLVABLE:
                    self._set_checks(func, anno_name, annotation)
                    if origin is Union:
                        self._build_union_des(func, annotation, namespace)
                    elif checks.isdatetype(origin):
                        self._build_date_des(func, anno_name, annotation)
                    elif checks.isuuidtype(origin):
                        self._build_uuid_des(func, anno_name, annotation)
                    elif origin in {Pattern, re.Pattern}:  # type: ignore
                        self._build_pattern_des(func, anno_name)
                    elif issubclass(origin, pathlib.Path):
                        self._build_path_des(func, anno_name)
                    elif not args and checks.isbuiltintype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.isfromdictclass(origin):
                        self._build_fromdict_des(func, anno_name)
                    elif checks.isenumtype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.istypeddict(origin):
                        self._build_typeddict_des(
                            func,
                            anno_name,
                            annotation,
                            total=origin.__total__,  # type: ignore
                            namespace=namespace,
                        )
                    elif checks.istypedtuple(origin) or checks.isnamedtuple(origin):
                        self._build_typedtuple_des(
                            func, anno_name, annotation, namespace=namespace
                        )
                    elif not args and checks.isbuiltinsubtype(origin):
                        self._build_builtin_des(func, anno_name, annotation)
                    elif checks.ismappingtype(origin):
                        self._build_mapping_des(
                            func, anno_name, annotation, namespace=namespace
                        )
                    elif checks.iscollectiontype(origin):
                        self._build_collection_des(
                            func, anno_name, annotation, namespace=namespace
                        )
                    else:
                        self._build_generic_des(
                            func, anno_name, annotation, namespace=namespace
                        )
                func.l(f"{gen.Keyword.RET} {self.VNAME}")
        deserializer = main.compile(ns=ns, name=func_name)
        return deserializer

    def _check_varargs(
        self, anno: "Annotation", des: DeserializerT, validator: "const.ValidatorT"
    ) -> Tuple[DeserializerT, "const.ValidatorT"]:
        if anno.parameter.kind == VAR_POSITIONAL:
            __des = des
            __validator = validator

            def des(__val, *, __des=__des):
                return (*(__des(x) for x in __val),)

            def validator(value, *, field: str = None, __validator=__validator):  # type: ignore
                return (*(__validator(x, field=field) for x in value),)

        elif anno.parameter.kind == VAR_KEYWORD:
            __des = des
            __validator = validator

            def des(__val, *, __des=__des):
                return {x: __des(y) for x, y in __val.items()}

            def validator(value, *, field: str = None, __validator=__validator):  # type: ignore
                return {x: __validator(y, field=field) for x, y in value.items()}

        return des, validator

    def _finalize_validator(
        self,
        constr: Optional["const.ConstraintsT"],
    ) -> "const.ValidatorT":
        def validate(value, *, field: str = None):
            return value

        if constr:
            validate = constr.validate  # noqa: F811

        return validate  # type: ignore

    def _finalize_deserializer(
        self,
        anno: "Annotation",
        des: DeserializerT,
        constr: Optional["const.ConstraintsT"],
    ) -> Tuple[DeserializerT, "const.ValidatorT"]:
        # Determine how to run in "strict-mode"
        validator = self._finalize_validator(constr)
        # Handle *args and **kwargs
        des, validator = self._check_varargs(anno, des, validator)
        # If we have type constraints, override the deserializer for strict annotations.
        if isinstance(constr, (const.TypeConstraints, const.LiteralConstraints)):
            if anno.strict:
                des = validator  # type: ignore
            elif isinstance(constr, const.LiteralConstraints):
                __d = des

                def des(val: Any, *, __d=__d, __v=validator) -> ObjectT:
                    return __v(__d(val))

        # Otherwise
        else:
            # In strict mode, we validate & coerce if there are constraints
            if anno.strict and constr and constr.coerce:
                __d = des

                def des(val: Any, *, __d=__d, __v=validator) -> ObjectT:
                    return __d(__v(val))

            elif anno.strict:
                des = validator  # type: ignore

        return des, validator

    def factory(
        self,
        annotation: "Annotation",
        constr: Optional["const.ConstraintsT"] = None,
        namespace: Type = None,
    ) -> Tuple[DeserializerT, "const.ValidatorT"]:
        annotation.serde = annotation.serde or SerdeConfig()
        key = self._get_name(annotation, constr)
        if key in self.__DES_CACHE:
            return self.__DES_CACHE[key]
        deserializer: Optional[DeserializerT] = None
        for check, des in self.__USER_DESS:
            if check(annotation.resolved):
                deserializer = des
                break
        if not deserializer:
            deserializer = self._build_des(annotation, key, namespace)

        deserializer, validator = self._finalize_deserializer(
            annotation, deserializer, constr
        )
        self.__DES_CACHE[key] = (deserializer, validator)

        return deserializer, validator
